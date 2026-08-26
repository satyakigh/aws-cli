# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for scripts/demo-cfn-validate.

The demo is an extensionless executable, so it is loaded as a module with a
SourceFileLoader (the same technique the other script tests use). These tests
exercise only the pure, offline pieces -- the validator output parser and the
Markdown report renderer (including its percentage math). No subprocess,
network, model, or integrated AWS CLI is involved: every input is a literal
string or a hand-built observation record.
"""

import importlib.machinery
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / 'scripts' / 'demo-cfn-validate'


def _load_demo():
    loader = importlib.machinery.SourceFileLoader(
        'demo_cfn_validate', str(DEMO_PATH)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


demo = _load_demo()


def _diag(severity, message='msg', property_path='none'):
    return {
        'severity': severity,
        'message': message,
        'property_path': property_path,
    }


def _record(
    name,
    description='a demo case',
    command='aws --validate-only s3api create-bucket --bucket b',
    classification='SYNTHESIZED_CREATE',
    status='VALIDATED',
    diagnostics=None,
    outcome='CLEAN',
    exit_code=0,
):
    return {
        'name': name,
        'description': description,
        'command': command,
        'classification': classification,
        'status': status,
        'diagnostics': diagnostics or [],
        'outcome': outcome,
        'exit_code': exit_code,
    }


# --- 1. Output parser: only what the validator printed is recorded ----------


def _clean_validated_block():
    # A CLEAN VALIDATED block whose modeled_template JSON lines must never be
    # misread as diagnostics.
    return '\n'.join(
        [
            '[cloudformation-validate] --- validate-only result ---',
            '[cloudformation-validate] classification: SYNTHESIZED_CREATE',
            '[cloudformation-validate] status: VALIDATED',
            '[cloudformation-validate] template_source: SYNTHESIZED',
            '[cloudformation-validate] detected_resources: AWS::S3::Bucket',
            '[cloudformation-validate] reason: synthesized from create-bucket',
            '[cloudformation-validate] modeled_template:',
            '[cloudformation-validate]   {',
            '[cloudformation-validate]     "Resources": {',
            '[cloudformation-validate]       "Bucket": {',
            '[cloudformation-validate]         "Type": "AWS::S3::Bucket"',
            '[cloudformation-validate]       }',
            '[cloudformation-validate]     }',
            '[cloudformation-validate]   }',
            '[cloudformation-validate] diagnostics: none',
            '[cloudformation-validate] outcome: CLEAN',
            '[cloudformation-validate] --- end validate-only ---',
        ]
    )


def test_parse_clean_validated_block_has_no_diagnostics():
    parsed = demo._parse_validation_output(_clean_validated_block())
    assert parsed['classification'] == 'SYNTHESIZED_CREATE'
    assert parsed['status'] == 'VALIDATED'
    # The template JSON lines are never mistaken for diagnostics.
    assert parsed['diagnostics'] == []


def test_parse_findings_block_extracts_each_severity_and_path():
    text = '\n'.join(
        [
            '[cloudformation-validate] --- validate-only result ---',
            '[cloudformation-validate] classification: EXPLICIT_TEMPLATE',
            '[cloudformation-validate] status: VALIDATED',
            '[cloudformation-validate] template_source: TEMPLATE_BODY',
            '[cloudformation-validate] detected_resources: AWS::S3::Bucket',
            '[cloudformation-validate] reason: template body provided',
            '[cloudformation-validate] modeled_template: none',
            '[cloudformation-validate] diagnostics: 2 finding(s)',
            '[cloudformation-validate]   ERROR: AccessControl PublicRead '
            'requires OwnershipControls [property_path: '
            'Resources/Bucket/Properties/AccessControl]',
            '[cloudformation-validate]   WARN: public access is risky '
            '[property_path: none]',
            '[cloudformation-validate] outcome: FINDINGS',
            '[cloudformation-validate] --- end validate-only ---',
        ]
    )
    parsed = demo._parse_validation_output(text)
    assert parsed['classification'] == 'EXPLICIT_TEMPLATE'
    assert parsed['status'] == 'VALIDATED'
    assert parsed['diagnostics'] == [
        {
            'severity': 'ERROR',
            'message': 'AccessControl PublicRead requires OwnershipControls',
            'property_path': 'Resources/Bucket/Properties/AccessControl',
        },
        {
            'severity': 'WARN',
            'message': 'public access is risky',
            'property_path': 'none',
        },
    ]


def test_parse_skipped_status():
    text = '\n'.join(
        [
            '[cloudformation-validate] --- validate-only result ---',
            '[cloudformation-validate] classification: READ_ONLY',
            '[cloudformation-validate] status: SKIPPED',
            '[cloudformation-validate] reason: read-only operation',
            '[cloudformation-validate] diagnostics: none',
            '[cloudformation-validate] outcome: CLEAN',
            '[cloudformation-validate] --- end validate-only ---',
        ]
    )
    parsed = demo._parse_validation_output(text)
    assert parsed['status'] == 'SKIPPED'
    assert parsed['diagnostics'] == []


def test_parse_missing_block_stays_unknown():
    # An unexpected ERROR that never rendered a block: nothing is inferred.
    parsed = demo._parse_validation_output(
        'Traceback (most recent call last):\nRuntimeError: build fault\n'
    )
    assert parsed['classification'] == 'unknown'
    assert parsed['status'] == 'unknown'
    assert parsed['diagnostics'] == []
    # Empty input is equally safe.
    empty = demo._parse_validation_output('')
    assert empty == {
        'classification': 'unknown',
        'status': 'unknown',
        'diagnostics': [],
    }


def test_parse_unrecognized_status_normalizes_to_unknown():
    text = '\n'.join(
        [
            '[cloudformation-validate] classification: SYNTHESIZED_CREATE',
            '[cloudformation-validate] status: MYSTERY',
            '[cloudformation-validate] diagnostics: none',
            '[cloudformation-validate] outcome: CLEAN',
        ]
    )
    parsed = demo._parse_validation_output(text)
    # A status outside the known set is not passed through; it stays unknown.
    assert parsed['status'] == 'unknown'


def test_parse_diagnostic_message_with_brackets_splits_at_property_path():
    # A message containing brackets must still split at the trailing,
    # anchored property_path suffix (greedy message capture).
    text = '\n'.join(
        [
            '[cloudformation-validate] status: VALIDATED',
            '[cloudformation-validate] diagnostics: 1 finding(s)',
            '[cloudformation-validate]   FATAL: bad value [see docs] here '
            '[property_path: /Resources/Bucket]',
            '[cloudformation-validate] outcome: FINDINGS',
        ]
    )
    parsed = demo._parse_validation_output(text)
    assert parsed['diagnostics'] == [
        {
            'severity': 'FATAL',
            'message': 'bad value [see docs] here',
            'property_path': '/Resources/Bucket',
        }
    ]


# --- 2. Percentage math (nontrivial rounding, visible denominator) ----------


def test_pct_formats_percentage_with_fraction():
    assert demo._pct(1, 2) == '50% (1/2)'
    assert demo._pct(0, 2) == '0% (0/2)'
    assert demo._pct(2, 2) == '100% (2/2)'
    # An empty denominator never reads as a real 0%.
    assert demo._pct(0, 0) == 'n/a (0/0)'
    # Nontrivial, repeating-decimal rounding.
    assert demo._pct(2, 3) == '67% (2/3)'
    assert demo._pct(1, 3) == '33% (1/3)'
    assert demo._pct(1, 6) == '17% (1/6)'
    assert demo._pct(5, 6) == '83% (5/6)'
    assert demo._pct(5, 16) == '31% (5/16)'
    assert demo._pct(7, 24) == '29% (7/24)'


# --- 3. Table cell helpers --------------------------------------------------


def test_md_cell_escapes_pipes_and_newlines():
    assert demo._md_cell('a | b') == 'a \\| b'
    assert demo._md_cell('line1\nline2') == 'line1 line2'
    assert demo._md_cell('crlf\r\nend') == 'crlf end'


def test_diagnostics_cell_summarizes_by_severity_in_order():
    assert demo._diagnostics_cell([]) == 'none'
    cell = demo._diagnostics_cell(
        [_diag('WARN'), _diag('FATAL'), _diag('WARN')]
    )
    # Ordered FATAL/ERROR/WARN, with counts, and the total leading it.
    assert cell == '3 (1 FATAL, 2 WARN)'


# --- 4. Report renderer: derived solely from observed records ---------------


def _mixed_records():
    """Six records giving nontrivial outcome/status/severity percentages.

    Outcomes: 3 CLEAN, 2 FINDINGS, 1 ERROR over 6 -> 50% / 33% / 17%.
    Statuses: 4 VALIDATED, 1 SKIPPED, 1 unknown over 6 -> 67% / 17% / 17%.
    A SKIPPED case still exits 0 (CLEAN outcome), so status and outcome are
    independent. One ERROR case never rendered a block (status unknown).
    """
    return [
        _record('s3-create-valid'),
        _record('sns-create-topic-valid'),
        _record(
            'read-only-list-buckets',
            classification='READ_ONLY',
            status='SKIPPED',
            outcome='CLEAN',
            exit_code=0,
        ),
        _record(
            's3-create-invalid',
            diagnostics=[_diag('FATAL')],
            outcome='FINDINGS',
            exit_code=252,
        ),
        _record(
            'cfn-s3-access-control-no-ownership',
            diagnostics=[_diag('ERROR'), _diag('WARN')],
            outcome='FINDINGS',
            exit_code=252,
        ),
        _record(
            'mystery-error',
            classification='unknown',
            status='unknown',
            outcome='ERROR',
            exit_code=254,
        ),
    ]


def test_render_report_structure_purpose_and_percentages():
    meta = {
        'generated_at': '2026-08-25T00:00:00-06:00',
        'aws_executable': '/tmp/build/aws',
    }
    report = demo._render_report(_mixed_records(), meta)

    # Title and every required section heading.
    assert report.startswith(
        '# cloudformation-validate diagnostic stimulus report'
    )
    for heading in (
        '## Executive summary',
        '## Diagnostics by severity',
        '## Per-case results',
        '## Severity meanings and method',
        '## Related generated reports',
    ):
        assert heading in report

    # Purpose / no-agent statement, and the explicit not-AI-behavior framing.
    assert '**No agent runs here**' in report
    assert 'deterministic stimulus case mix' in report
    assert 'a measure of any agent or AI behavior' in report

    # Run timestamp and the exact selected cases.
    assert '- Generated: 2026-08-25T00:00:00-06:00' in report
    assert '- AWS CLI: `/tmp/build/aws`' in report
    assert 'Cases executed (6):' in report
    assert '`s3-create-valid`' in report

    # Executive percentages + k/N for the outcome and status distributions.
    assert '- CLEAN: 50% (3/6)' in report
    assert '- FINDINGS: 33% (2/6)' in report
    assert '- ERROR: 17% (1/6)' in report
    assert '- VALIDATED: 67% (4/6)' in report
    assert '- SKIPPED: 17% (1/6)' in report
    assert '- unknown: 17% (1/6)' in report


def test_render_report_severity_counts_and_per_case_table():
    report = demo._render_report(
        _mixed_records(),
        {'generated_at': 't', 'aws_executable': 'aws'},
    )

    # Severity case/diagnostic counts: one case and one diagnostic each.
    assert '3 diagnostic(s) were' in report
    assert '| FATAL | 1 | 1 |' in report
    assert '| ERROR | 1 | 1 |' in report
    assert '| WARN | 1 | 1 |' in report

    # Per-case table header and rows, including the ERROR case (report is
    # written even with an unexpected ERROR outcome).
    assert (
        '| Case | Description | Command | Classification | Status | '
        'Diagnostics | Outcome | Exit |'
    ) in report
    assert '| mystery-error |' in report
    # The multi-severity diagnostics cell is summarized and ordered.
    assert '2 (1 ERROR, 1 WARN)' in report
    # Exit codes are carried through verbatim.
    assert '| FINDINGS | 252 |' in report
    assert '| ERROR | 254 |' in report


def test_render_report_method_and_related_reports():
    report = demo._render_report(
        _mixed_records(),
        {'generated_at': 't', 'aws_executable': 'aws'},
    )

    # Severity meanings.
    assert '**FATAL**' in report
    assert '**ERROR**' in report
    assert '**WARN**' in report

    # Offline / credential-free / no-HTTP method statement.
    assert 'offline' in report
    assert 'credential-free' in report
    assert 'no HTTP call' in report

    # Names/links for all three generated reports, including the other two.
    assert 'scripts/cfn-validate-report.md' in report
    assert 'scripts/s3-agent-loop-report.md' in report
    assert 'scripts/s3-agent-safety-report.html' in report


def test_render_report_handles_empty_denominator():
    # No records at all: percentages read as n/a, never a misleading 0%.
    report = demo._render_report(
        [], {'generated_at': 't', 'aws_executable': 'aws'}
    )
    assert 'Cases executed (0): (none)' in report
    assert '- CLEAN: n/a (0/0)' in report
    assert '- VALIDATED: n/a (0/0)' in report
