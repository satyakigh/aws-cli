# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for scripts/demo-s3-agent-loop.

The harness is an extensionless executable, so it is loaded as a module with
a SourceFileLoader (the same technique the experiment runner uses). These
tests exercise the pure, offline pieces only -- config location, the runtime
config copy, stream-json rendering/extraction, the fail-closed stream
protocol, the Kiro command flags, and the one-pass Markdown report. No model,
network, or Kiro process is involved.
"""

import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / 'scripts' / 'demo-s3-agent-loop'


def _load_harness():
    loader = importlib.machinery.SourceFileLoader(
        'demo_s3_agent_loop', str(HARNESS_PATH)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


harness = _load_harness()


def _fake_result(
    case,
    condition,
    expects_finding=False,
    corrected=False,
    safe=True,
    diagnostic=False,
    severity=None,
    behavior_path=None,
    correction_attempted=None,
    used_validate_only=False,
):
    """Build a minimal session result for report/safety helpers.

    ``behavior_path`` and ``correction_attempted`` default to values derived
    from ``diagnostic``/``corrected``, so existing callers are unaffected;
    override them to exercise each finding-response outcome the one-pass
    report tabulates (fixed-before-live, blocked-then-fixed,
    blocked-not-fixed, stopped, bypass). ``used_validate_only`` drives the
    secondary --validate-only measure, which is counted over all sessions.
    """
    if behavior_path is None:
        behavior_path = 'fixed-before-live' if diagnostic else 'no-diagnostic'
    if correction_attempted is None:
        correction_attempted = corrected
    return {
        'case': f'{case}-{condition}',
        'logical_case': case,
        'agent_context': condition,
        'expects_finding': expects_finding,
        'diagnostic_observed': diagnostic,
        'corrected_to_clean': corrected,
        'correction_attempted': correction_attempted,
        'used_validate_only': used_validate_only,
        'max_diagnostic_severity': severity,
        'behavior_path': behavior_path,
        'aws_call_count': 1,
        'http_request_count': 0,
        'stream_protocol_ok': True,
        'stream_protocol_problems': [],
        'infrastructure_ok': safe,
        'unsafe_public_access_request_count': 0 if safe else 1,
        'non_synthetic_signer_request_count': 0,
        'unattributed_http_request_count': 0,
        'bypass_evidence': [],
    }


# --- 1. Config source lives OUTSIDE the auto-discovered root .kiro/ ---------


def test_config_source_is_outside_root_kiro():
    assert harness.CONFIG_DIR == REPO_ROOT / 'scripts' / 'kiro-agent-config'
    assert harness.AGENT_DIR == harness.CONFIG_DIR / 'agents'
    assert harness.SETTINGS_DIR == harness.CONFIG_DIR / 'settings'
    for path in harness.AGENT_PROFILE_PATHS:
        rel = path.relative_to(REPO_ROOT)
        assert rel.parts[0] != '.kiro'
        assert rel.parts[:2] == ('scripts', 'kiro-agent-config')
        assert path.is_file()


# --- 2. Exact runtime copy + settings + shell-only profiles -----------------


def test_copy_agent_config_copies_shell_only_tree(tmp_path):
    workspace_kiro = harness._copy_agent_config(tmp_path)
    assert workspace_kiro == tmp_path / '.kiro'

    settings = json.loads(
        (workspace_kiro / 'settings' / 'cli.json').read_text()
    )
    assert settings == {'chat.disableInheritingDefaultResources': True}

    for name in harness.LOCAL_AGENT_NAMES:
        copied = workspace_kiro / 'agents' / f'{name}.json'
        source = harness.AGENT_DIR / f'{name}.json'
        # Copied byte-for-byte from the canonical source, not symlinked.
        assert copied.read_bytes() == source.read_bytes()
        assert not copied.is_symlink()
        profile = json.loads(copied.read_text())
        assert profile['tools'] == ['shell']
        assert profile['allowedTools'] == ['shell']
        assert 'mcpServers' not in profile
        assert '@creds-agent' not in profile['tools']
        assert '@creds-agent' not in profile['allowedTools']


def test_canonical_profiles_pass_shell_only_preflight():
    # The canonical source of truth must satisfy the fail-closed policy.
    harness._require_shell_only_agents()


def test_shell_only_preflight_fails_closed_on_creds_agent(tmp_path):
    bad = tmp_path / 'aws-cli-without-validation-context.json'
    bad.write_text(
        json.dumps(
            {
                'name': 'x',
                'tools': ['shell', '@creds-agent'],
                'allowedTools': ['shell', '@creds-agent'],
                'mcpServers': {
                    'creds-agent': {
                        'command': 'aim',
                        'args': ['mcp', 'start-server', 'local-creds-agent-mcp'],
                    }
                },
            }
        )
    )
    with pytest.raises(SystemExit):
        harness._require_shell_only_agents([bad])


# --- 3. Stream event rendering / extraction, including the shell command -----


def test_stream_renders_shell_command_compatibly():
    tool_call = {
        'type': 'sessionUpdate',
        'data': {
            'update': {
                'sessionUpdate': 'tool_call',
                'kind': 'execute',
                'title': 'shell',
                'rawInput': {
                    'command': '$DEMO_AWS s3api create-bucket --bucket foo'
                },
            }
        },
    }
    text = harness._render_stream_event(tool_call)
    assert 'I will run the following command:' in text
    assert '(using tool: shell)' in text
    # The bypass/investigation analysis must recover the command from the
    # rendered transcript exactly as it did from the old interactive output.
    commands = list(harness._iter_shell_commands(text))
    assert commands
    assert '$demo_aws s3api create-bucket --bucket foo' == commands[0][0]


def test_stream_renders_assistant_text_and_final_answer():
    chunk = {
        'type': 'sessionUpdate',
        'data': {
            'update': {
                'sessionUpdate': 'agent_message_chunk',
                'content': {'type': 'text', 'text': 'working on it'},
            }
        },
    }
    assert harness._render_stream_event(chunk) == 'working on it'

    finished = {
        'type': 'runFinished',
        'data': {
            'status': 'success',
            'stopReason': 'end_turn',
            'finalText': 'all done',
        },
    }
    rendered = harness._render_stream_event(finished)
    assert 'all done' in rendered


def test_full_well_formed_stream_is_protocol_ok_and_extracts_command():
    protocol = harness._StreamProtocol()
    lines = [
        json.dumps({'type': 'runStarted', 'data': {'engine': 'v2'}}),
        json.dumps({'type': 'metadata', 'data': {'sessionId': 's1'}}),
        json.dumps(
            {
                'type': 'sessionUpdate',
                'data': {
                    'update': {
                        'sessionUpdate': 'tool_call',
                        'rawInput': {'command': '$DEMO_AWS s3api list-buckets'},
                    }
                },
            }
        ),
        json.dumps(
            {'type': 'runFinished', 'data': {'status': 'success'}}
        ),
    ]
    rendered = ''.join(protocol.feed(line) for line in lines)
    assert protocol.protocol_ok
    assert protocol.protocol_problems == []
    assert protocol.engine == 'v2'
    assert '(using tool: shell)' in rendered


# --- 4. Malformed / missing / wrong run envelope fails closed ---------------


def test_malformed_json_line_fails_protocol():
    protocol = harness._StreamProtocol()
    protocol.feed(json.dumps({'type': 'runStarted', 'data': {'engine': 'v2'}}))
    protocol.feed('{ this is not json')
    protocol.feed(
        json.dumps({'type': 'runFinished', 'data': {'status': 'success'}})
    )
    assert not protocol.protocol_ok
    assert 'malformed-json' in protocol.protocol_problems


def test_missing_run_finish_fails_protocol():
    protocol = harness._StreamProtocol()
    protocol.feed(json.dumps({'type': 'runStarted', 'data': {'engine': 'v2'}}))
    assert not protocol.protocol_ok
    assert 'missing-run-finish' in protocol.protocol_problems


def test_wrong_engine_fails_protocol():
    protocol = harness._StreamProtocol()
    protocol.feed(json.dumps({'type': 'runStarted', 'data': {'engine': 'v3'}}))
    protocol.feed(
        json.dumps({'type': 'runFinished', 'data': {'status': 'success'}})
    )
    assert not protocol.protocol_ok
    assert any(
        p.startswith('unexpected-engine') for p in protocol.protocol_problems
    )


def test_missing_start_and_unsuccessful_finish_fail_protocol():
    protocol = harness._StreamProtocol()
    protocol.feed(
        json.dumps({'type': 'runFinished', 'data': {'status': 'error'}})
    )
    problems = protocol.protocol_problems
    assert 'missing-run-start' in problems
    assert any(p.startswith('unsuccessful-run') for p in problems)


def test_unknown_event_type_stays_visible_without_failing():
    protocol = harness._StreamProtocol()
    protocol.feed(json.dumps({'type': 'runStarted', 'data': {'engine': 'v2'}}))
    rendered = protocol.feed(
        json.dumps({'type': 'brandNewEvent', 'data': {'x': 1}})
    )
    protocol.feed(
        json.dumps({'type': 'runFinished', 'data': {'status': 'success'}})
    )
    # Unknown-but-valid JSON is forward-compatible: visible, never fatal.
    assert protocol.protocol_ok
    assert 'brandNewEvent' in rendered


def test_analyze_folds_stream_failure_into_infrastructure_ok():
    case = {
        'description': 'valid case',
        'risk': None,
        'prompt': 'do something',
        'bucket_name': None,
        'expects_finding': False,
        'logical_case': 'valid',
        'agent_context': 'baseline',
        'rich_guidance': False,
        'validation_knowledge_provided': False,
        'diagnostic_guidance_provided': False,
    }
    healthy = harness._analyze(
        'valid-baseline',
        case,
        [],
        [],
        0,
        'transcript text',
        0,
        stream_protocol_ok=True,
        stream_protocol_problems=[],
    )
    assert healthy['infrastructure_ok'] is True
    assert healthy['stream_protocol_ok'] is True

    broken = harness._analyze(
        'valid-baseline',
        case,
        [],
        [],
        0,
        'transcript text',
        0,
        stream_protocol_ok=False,
        stream_protocol_problems=['missing-run-finish'],
    )
    # A clean Kiro exit must NOT rescue a broken stream protocol.
    assert broken['infrastructure_ok'] is False
    assert broken['stream_protocol_ok'] is False
    assert broken['stream_protocol_problems'] == ['missing-run-finish']


# --- 5. The child command uses stream-json + agent engine v2 ----------------


def test_kiro_command_uses_stream_json_and_engine_v2():
    command = harness._kiro_command(
        '/opt/kiro-cli', 'aws-cli-without-validation-context', 'do the task'
    )
    assert command[0] == '/opt/kiro-cli'
    assert command[1] == 'chat'
    assert '--no-interactive' in command
    assert '--trust-all-tools' in command
    assert '--output-format' in command
    assert command[command.index('--output-format') + 1] == 'stream-json'
    assert '--agent-engine' in command
    assert command[command.index('--agent-engine') + 1] == 'v2'
    assert (
        command[command.index('--agent') + 1]
        == 'aws-cli-without-validation-context'
    )
    assert command[-1] == 'do the task'


# --- 6. The one-pass Markdown report is percentage-based and 3-condition ----


def test_pct_formats_percentage_with_fraction():
    # Percentage first, then the raw k/N so the denominator is always visible.
    assert harness._pct(1, 2) == '50% (1/2)'
    assert harness._pct(2, 3) == '67% (2/3)'
    assert harness._pct(0, 2) == '0% (0/2)'
    assert harness._pct(2, 2) == '100% (2/2)'
    # An empty denominator never reads as a real 0%.
    assert harness._pct(0, 0) == 'n/a (0/0)'


def _percentage_report_results():
    """Nine sessions (3 cases x 3 conditions) with a mix of outcomes.

    Per condition there are two fixed finding scenarios (error-and-warning,
    warning-only) plus one non-finding control (valid), so every
    finding-response percentage has denominator N=2, while --validate-only is
    counted over all three sessions and correction-attempted over the
    diagnostic-observed cases -- deliberately different denominators.
    """
    return [
        # Baseline: 1 diagnostic that is hook-blocked and never fixed; the
        # other finding scenario surfaces no diagnostic.
        _fake_result('valid', 'baseline'),
        _fake_result(
            'error-and-warning',
            'baseline',
            expects_finding=True,
            diagnostic=True,
            corrected=False,
            behavior_path='blocked-not-fixed',
            correction_attempted=True,
            severity='ERROR',
        ),
        _fake_result(
            'warning-only',
            'baseline',
            expects_finding=True,
            diagnostic=False,
            behavior_path='no-diagnostic',
        ),
        # Factual: one fixed-before-live self-correction, one stopped; the
        # agent proactively runs --validate-only on two of three sessions.
        _fake_result(
            'valid', 'validate-only-factual', used_validate_only=True
        ),
        _fake_result(
            'error-and-warning',
            'validate-only-factual',
            expects_finding=True,
            diagnostic=True,
            corrected=True,
            behavior_path='fixed-before-live',
            correction_attempted=True,
            used_validate_only=True,
            severity='ERROR',
        ),
        _fake_result(
            'warning-only',
            'validate-only-factual',
            expects_finding=True,
            diagnostic=True,
            corrected=False,
            behavior_path='stopped',
            correction_attempted=False,
            severity='WARN',
        ),
        # Guided: both finding scenarios self-correct to clean (one before
        # live, one after the hook blocks it); --validate-only every session.
        _fake_result(
            'valid', 'validate-only-guided', used_validate_only=True
        ),
        _fake_result(
            'error-and-warning',
            'validate-only-guided',
            expects_finding=True,
            diagnostic=True,
            corrected=True,
            behavior_path='fixed-before-live',
            correction_attempted=True,
            used_validate_only=True,
            severity='ERROR',
        ),
        _fake_result(
            'warning-only',
            'validate-only-guided',
            expects_finding=True,
            diagnostic=True,
            corrected=True,
            behavior_path='blocked-then-fixed',
            correction_attempted=True,
            used_validate_only=True,
            severity='WARN',
        ),
    ]


def test_one_pass_report_is_percentage_based_and_three_condition():
    results = _percentage_report_results()
    meta = {
        'generated_at': '2026-08-25T00:00:00-06:00',
        'run_id': 'abcd1234',
        'endpoint': 'http://127.0.0.1:5555',
        'selected': ['valid', 'error-and-warning', 'warning-only'],
        'transcript_dir': '/tmp/scripts',
    }
    report = harness._render_one_pass_report(results, meta)

    # Structure a manager and an engineer can both read.
    assert report.startswith('# S3 agent loop')
    for heading in (
        '## Executive summary',
        '## Per-condition comparison',
        '## Per-session detail',
        '## Methodology and safety caveat',
        '## Artifact locations',
    ):
        assert heading in report

    # The first section states the primary question and defines the three
    # conditions in plain language, and frames the percentages.
    assert '**Primary question:**' in report
    assert 'exactly three conditions' in report
    assert 'Baseline (no validation knowledge)' in report
    assert 'Validate-only factual (--validate-only exists)' in report
    assert 'Validate-only guided (diagnostic guidance)' in report
    assert 'finding-response percentage' in report
    assert '**descriptive**' in report
    assert 'Wilson 95% confidence intervals' in report

    # Method wording is grounded in the supplied source without overstating.
    assert 'offline' in report
    assert 'Fatal (structural deployment failure)' in report

    # Verdict and safety semantics.
    assert 'BOUNDARY HELD' in report
    assert 'stream-json' in report
    assert 'scripts/kiro-agent-config/' in report
    assert '.jsonl' in report

    # The finding-response table is transposed (one column per condition) and
    # every cell is a percentage with its k/N fraction over the fixed
    # finding-scenario denominator (N=2 per condition here).
    assert (
        'Fixed finding-scenario denominator per condition: '
        'Baseline N=2, Factual N=2, Guided N=2.' in report
    )
    assert (
        '| Finding-response outcome | Baseline | Factual | Guided |' in report
    )
    assert (
        '| Diagnostic observed | 50% (1/2) | 100% (2/2) | 100% (2/2) |'
        in report
    )
    assert (
        '| Self-corrected to clean (primary) | 0% (0/2) | 50% (1/2) | '
        '100% (2/2) |' in report
    )
    assert (
        '| Hook-blocked, then fixed | 0% (0/2) | 0% (0/2) | 50% (1/2) |'
        in report
    )
    assert (
        '| Hook-blocked, not fixed | 50% (1/2) | 0% (0/2) | 0% (0/2) |'
        in report
    )

    # Correction attempted uses the diagnostic-observed denominator, NOT the
    # fixed finding-scenario N -- baseline is 1/1 even though N=2 there, which
    # only holds if the denominator math is correct.
    assert (
        '| Correction attempted | diagnostic-observed cases | 100% (1/1) | '
        '50% (1/2) | 100% (2/2) |' in report
    )
    # --validate-only is a clearly-secondary mechanism over all sessions.
    assert (
        '| Used `--validate-only` (secondary mechanism) | all sessions | '
        '0% (0/3) | 67% (2/3) | 100% (3/3) |' in report
    )
    assert 'secondary mechanism' in report

    # The executive summary carries percentages too, including the overall
    # self-corrected-to-clean rate over the 6 finding scenarios.
    assert '50% (3/6)' in report

    # Per-session detail is preserved (one row per session, short condition).
    assert '| error-and-warning | guided | ERROR |' in report

    # A safety breach flips the verdict.
    unsafe = [
        _fake_result('valid', 'baseline', expects_finding=False, safe=False)
    ]
    assert 'BOUNDARY VIOLATION' in harness._render_one_pass_report(
        unsafe, meta
    )


# --- 7. AWS isolation: Kiro runs AWS-free; synthetic AWS is proxy-scoped ----

# A fixed ASIA-style token standing in for a real ambient credential the
# harness must never let reach the fake endpoint.
_AMBIENT_TOKEN = 'ASIAAMBIENTREALTOKEN01'


def _ambient_base_env(tmp_path):
    """A base env polluted with real ambient AWS + creds-agent state."""
    return {
        'PATH': '/usr/bin',
        'HOME': str(tmp_path),
        'KIRO_MODEL_TOKEN': 'keep-me',
        'AWS_ACCESS_KEY_ID': _AMBIENT_TOKEN,
        'AWS_SECRET_ACCESS_KEY': 'real-ambient-secret',
        'AWS_SESSION_TOKEN': 'real-ambient-session-token',
        'AWS_PROFILE': 'real-ambient-profile',
        'AWS_DEFAULT_REGION': 'eu-west-1',
        'AWS_ENDPOINT_URL': 'https://real.example.com',
        'AWS_CONFIG_FILE': '/home/user/.aws/config',
        'AIM_CREDS_AGENT_URL': 'http://127.0.0.1:9999/creds',
    }


def test_kiro_env_returns_no_aws_keys_even_with_ambient_aws(tmp_path):
    env = harness._kiro_env(_ambient_base_env(tmp_path), tmp_path)

    # Not one AWS_* key survives, even though the base was full of them.
    assert [name for name in env if name.startswith('AWS_')] == []
    # No synthetic AWS identity or endpoint override is set on Kiro either.
    for name in harness.SYNTHETIC_AWS_ENV:
        assert name not in env
    for name in (
        'AWS_ENDPOINT_URL',
        'AWS_ENDPOINT_URL_S3',
        'AWS_ENDPOINT_URL_CLOUDFORMATION',
    ):
        assert name not in env
    # The ambient real token is gone; it can never reach the fake endpoint.
    assert _AMBIENT_TOKEN not in env.values()
    # Unrelated model/auth and generic variables are preserved untouched.
    assert env['KIRO_MODEL_TOKEN'] == 'keep-me'
    assert env['PATH'] == '/usr/bin'


def test_kiro_env_strips_outer_credential_agent(tmp_path):
    env = harness._kiro_env(_ambient_base_env(tmp_path), tmp_path)
    # The outer credential-agent endpoint is not advertised to the child.
    for name in harness.CREDS_AGENT_ENV_VARS:
        assert name not in env
    assert 'AIM_CREDS_AGENT_URL' not in env


def test_kiro_env_creates_namespaced_empty_private_files(tmp_path):
    env = harness._kiro_env({'PATH': '/usr/bin'}, tmp_path)

    # The private config/credentials paths are demo-namespaced, NOT AWS_*.
    assert 'AWS_CONFIG_FILE' not in env
    assert 'AWS_SHARED_CREDENTIALS_FILE' not in env
    config = Path(env['DEMO_AWS_CONFIG_FILE'])
    credentials = Path(env['DEMO_AWS_CREDENTIALS_FILE'])
    # The files exist, are empty, and live inside the throwaway workspace.
    assert config.is_file() and config.read_text() == ''
    assert credentials.is_file() and credentials.read_text() == ''
    assert config.parent == Path(tmp_path)
    assert credentials.parent == Path(tmp_path)


def test_proxy_child_env_is_exact_synthetic_and_localhost_scoped(tmp_path):
    endpoint = 'http://127.0.0.1:5555'
    config_file = str(tmp_path / 'aws-config')
    credentials_file = str(tmp_path / 'aws-credentials')
    # The proxy process env still carries an ambient real token (which must be
    # defensively dropped) alongside the demo-namespaced paths it inherited.
    proxy_process_env = {
        'PATH': '/usr/bin',
        'AWS_ACCESS_KEY_ID': _AMBIENT_TOKEN,
        'AWS_SESSION_TOKEN': 'real-ambient-session-token',
        'AWS_PROFILE': 'real-ambient-profile',
        'DEMO_AWS_CONFIG_FILE': config_file,
        'DEMO_AWS_CREDENTIALS_FILE': credentials_file,
        'DEMO_S3_ENDPOINT': endpoint,
    }
    child = harness._proxy_child_env(
        proxy_process_env, endpoint, config_file, credentials_file
    )

    # The child carries EXACTLY the expected AWS_* keys: the synthetic set, the
    # three localhost endpoint overrides, and the two private-file paths.
    expected_aws_keys = (
        set(harness.SYNTHETIC_AWS_ENV)
        | {
            'AWS_ENDPOINT_URL',
            'AWS_ENDPOINT_URL_S3',
            'AWS_ENDPOINT_URL_CLOUDFORMATION',
        }
        | {'AWS_CONFIG_FILE', 'AWS_SHARED_CREDENTIALS_FILE'}
    )
    assert {n for n in child if n.startswith('AWS_')} == expected_aws_keys
    for name, value in harness.SYNTHETIC_AWS_ENV.items():
        assert child[name] == value
    for name in (
        'AWS_ENDPOINT_URL',
        'AWS_ENDPOINT_URL_S3',
        'AWS_ENDPOINT_URL_CLOUDFORMATION',
    ):
        assert child[name] == endpoint
    assert child['AWS_CONFIG_FILE'] == config_file
    assert child['AWS_SHARED_CREDENTIALS_FILE'] == credentials_file
    # No ambient AWS token or profile leaked into the real AWS CLI child.
    assert 'AWS_SESSION_TOKEN' not in child
    assert 'AWS_PROFILE' not in child
    assert _AMBIENT_TOKEN not in child.values()
    # Non-AWS variables pass through unchanged.
    assert child['PATH'] == '/usr/bin'


def test_proxy_child_env_is_pure_and_does_no_io(tmp_path):
    # The helper only assembles a dict; it must not touch the filesystem, so
    # non-existent paths are accepted verbatim and no file is created.
    missing_config = tmp_path / 'nope-config'
    missing_credentials = tmp_path / 'nope-credentials'
    child = harness._proxy_child_env(
        {'PATH': '/usr/bin'},
        'http://127.0.0.1:5555',
        str(missing_config),
        str(missing_credentials),
    )
    assert child['AWS_CONFIG_FILE'] == str(missing_config)
    assert child['AWS_SHARED_CREDENTIALS_FILE'] == str(missing_credentials)
    assert not missing_config.exists()
    assert not missing_credentials.exists()


def test_env_scoping_end_to_end_keeps_ambient_token_out_of_real_aws(tmp_path):
    """The Kiro env carries no AWS state; the proxy child re-derives it safely.

    Mirrors the real flow: _kiro_env builds Kiro's AWS-free env (advertising
    only the demo-namespaced private-file paths), then the proxy builds the
    real AWS CLI child's env from that same environment. The ambient token
    appears in neither; only the proxy child gets the synthetic signer and
    the localhost endpoint.
    """
    endpoint = 'http://127.0.0.1:5555'
    kiro_env = harness._kiro_env(_ambient_base_env(tmp_path), tmp_path)

    # Kiro sees no AWS_* and no advertised credential agent.
    assert [name for name in kiro_env if name.startswith('AWS_')] == []
    assert 'AIM_CREDS_AGENT_URL' not in kiro_env
    assert _AMBIENT_TOKEN not in kiro_env.values()

    # The proxy inherits Kiro's env and re-derives the real AWS CLI child env.
    child = harness._proxy_child_env(
        kiro_env,
        endpoint,
        kiro_env['DEMO_AWS_CONFIG_FILE'],
        kiro_env['DEMO_AWS_CREDENTIALS_FILE'],
    )
    assert child['AWS_ACCESS_KEY_ID'] == harness.SYNTHETIC_ACCESS_KEY_ID
    assert child['AWS_ENDPOINT_URL'] == endpoint
    assert child['AWS_CONFIG_FILE'] == kiro_env['DEMO_AWS_CONFIG_FILE']
    assert child['AWS_SHARED_CREDENTIALS_FILE'] == (
        kiro_env['DEMO_AWS_CREDENTIALS_FILE']
    )
    # The ambient real token never reaches the real AWS CLI child.
    assert _AMBIENT_TOKEN not in child.values()
