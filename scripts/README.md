# AWS CLI CloudFormation validation demos

This directory documents the `cloudformation-validate` integration in this AWS
CLI v2 checkout and the scripts that exercise it. The integration validates
requests in process, reports diagnostics at `WARN` severity or higher, and
blocks requests with findings before transport.

Run all commands from the repository root. The main experiment is:

```text
python3 scripts/run-s3-agent-safety-experiment
```

## Quick reference

| Goal | Command | Main output |
|---|---|---|
| Inspect the validator without an agent | `python3 scripts/demo-cfn-validate` | `scripts/cfn-validate-report.md` |
| Run every agent condition once | `python3 scripts/demo-s3-agent-loop` | `scripts/s3-agent-loop-report.md` |
| Run repeated trials with confidence intervals | `python3 scripts/run-s3-agent-safety-experiment` | `scripts/s3-agent-safety-report.md` |
| Regenerate the aggregate report without agents | `python3 scripts/run-s3-agent-safety-experiment --from-data` | Rewrites the aggregate report from `trials.json` |

Requirements:

* Python 3.9 or newer.
* Kiro CLI installed and authenticated for the two agent-based commands. The
  validator-only command does not use Kiro.
* An AWS CLI source checkout containing `scripts/kiro-agent-config/`.
* A build-capable Python environment. The scripts discover an existing
  integrated AWS CLI build or build one on first use, which can take several
  minutes.
* No AWS credentials are required. The validator-only demo is credential-free;
  the agent demos use a fixed synthetic identity and a localhost endpoint.

## Validation integration and command behavior

`cloudformation-validate==1.8.0` is a pinned runtime dependency. Its wheel is
stored under `requirements/wheels/`, installed without a package index, and
bundled into the PyInstaller executable.

At runtime, `awscli/customizations/cfnvalidate/` adds the global
`--validate-only` option and a generic request hook that runs before request
serialization and transport. The hook validates locally with a cached
`RegoEngine` at the `WARN` threshold. It does not call a service API such as
CloudFormation `ValidateTemplate`.

| `--validate-only` | Validation result | CLI output | Return code | HTTP request |
|---|---|---|---:|---|
| yes | clean | `CLEAN` | 0 | no |
| yes | findings | `FINDINGS` plus diagnostics | 252 | no |
| yes | skipped because the request is not modeled | `CLEAN` with `SKIPPED` status | 0 | no |
| no | clean | normal command output | normal CLI return code | yes |
| no | findings | diagnostics and `ParamValidationError` | 252 | no |
| no | skipped because the request is not modeled | normal command output | normal CLI return code | yes |

Return code `252` is the AWS CLI parameter-validation code. Parsing,
authentication, service, and other non-validation errors keep their standard
AWS CLI behavior and return codes.

## Agent conditions and profile placement

Every agent session receives the same task, shell-only permissions, and
`$DEMO_AWS` command wrapper. Only the validation information differs:

| Condition | Agent profile | Information and instructions |
|---|---|---|
| Baseline | `aws-cli-without-validation-context` | No information about `cloudformation-validate` or `--validate-only`. |
| Validation information only | `aws-cli-with-validate-only-context` | Knows that `--validate-only` validates locally, prints diagnostics, and sends no request; receives no instruction to use it or correct findings. |
| Validation information and correction instructions | `aws-cli-with-validate-only-diagnostic-guidance` | Receives the same information plus diagnostic interpretation and instructions to correct the same operation and validate again before live execution. |

The canonical profiles are under `scripts/kiro-agent-config/agents/`, not the
repository root `.kiro/`. Kiro automatically discovers root `.kiro/`
configuration, so placing experiment profiles there could change unrelated
sessions. Before each run, the harness verifies that every profile exposes
only the shell and has no MCP servers, powers, resources, or hooks. It then
copies the complete configuration into an isolated temporary workspace.

## Safety model

Kiro itself receives no `AWS_*` variables and cannot access the outer
credential agent. The `$DEMO_AWS` wrapper:

* permits only `s3api create-bucket` and `cloudformation create-stack`;
* rejects `--profile` and any endpoint other than its generated
  `http://127.0.0.1:<port>` endpoint;
* starts the integrated CLI with fixed synthetic credentials, disabled IMDS
  and retries, and empty private config and credentials files; and
* records each command before forwarding it.

The local endpoint accepts only the exact synthetic SigV4 signer and rejects
unsigned or differently signed requests. The harness correlates every endpoint
request with a wrapped command and rechecks the records when generating the
report. A non-local endpoint, unexpected signer, untracked endpoint request,
transport from `--validate-only`, unsafe request, or observed wrapper bypass
fails the run. These failures are enforced whether or not `--strict` is used;
`--strict` additionally requires every session to issue at least one AWS
command.

The verified guarantee is limited to observed AWS command paths: they use no
real AWS credentials and call no remote AWS service. This is not
operating-system-level network isolation; Kiro still needs its model
connection. A shell-only agent could try `$DEMO_REAL_AWS` directly. The
transcript analysis detects and fails an observed attempt, but does not prevent
it at the operating-system level.

## Validator-only demo

```text
python3 scripts/demo-cfn-validate
```

This command runs 24 deterministic requests covering valid, invalid, and
unmodeled operations across S3, SNS, SQS, Lambda, CloudFormation, DynamoDB,
EC2, and Cloud Control. It strips inherited AWS configuration and uses an unused
localhost endpoint. Because every command uses `--validate-only`, no request is
signed or sent.

For each case, it prints the classification, validation status, modeled
template, diagnostics, outcome, and process return code. Expected `CLEAN`
(return code `0`) and `FINDINGS` (return code `252`) outcomes allow the demo to
exit `0`. Any other case return code is reported as `ERROR` and makes the demo
exit nonzero after all selected cases finish.

Useful options:

* `--case NAME` runs one case.
* `--aws PATH` selects an integrated AWS CLI executable.
* `--report PATH` changes the Markdown report path.

The report is generated from that run's observed output and is written even
when a case has an unexpected error.

## One-pass agent demo

```text
python3 scripts/demo-s3-agent-loop
```

This command runs every selected case once under all three agent conditions.
The standalone default includes nine cases: `valid`, `warning-only`,
`error-and-warning`, `fatal-underscore`, `fatal-uppercase`,
`fatal-terminal-hyphen`, `fatal-overlength`, `fatal-multidefect`, and
`staged-multi-finding`.

The default console output is one line per session. Each session also writes a
readable `.txt` transcript and the raw stream-json `.jsonl` events. Use
`--verbose` to stream the full agent output, reconstructed AWS command trace,
and detailed session summary.

Useful options:

* `--list-cases` lists cases without launching Kiro.
* `--case NAME` is repeatable and runs the selected case under all conditions.
* `--strict` also fails a session that issued no AWS command.
* `--timeout N` changes the 300-second per-session timeout.
* `--report PATH`, `--results-json PATH`, and `--transcript-dir PATH` change
  artifact locations.
* `--aws PATH` and `--kiro-cli PATH` select executables.

The harness always writes a one-pass Markdown report. Percentages describe one
observation per case and condition; they are not repeated-trial estimates.

## Repeated experiment

```text
python3 scripts/run-s3-agent-safety-experiment
```

This is the primary command. By default it runs 54 sessions: three repetitions
of six cases under three conditions. It aggregates the structured session data
and reports rates with Wilson 95% confidence intervals.

Default cases:

* `valid` — clean S3 `CreateBucket` control.
* `warning-only` — CloudFormation S3 `AccessControl` warning.
* `error-and-warning` — CloudFormation S3 error and warning.
* `fatal-overlength` — S3 bucket name longer than 63 characters.
* `fatal-multidefect` — S3 bucket name with multiple format violations.
* `staged-multi-finding` — CloudFormation S3 template with fatal, error, and
  warning diagnostics.

Useful options:

* `--repetitions N` changes the default of three.
* `--case NAME` is repeatable. The runner accepts the six defaults plus
  `fatal-underscore`, `fatal-uppercase`, and `fatal-terminal-hyphen`.
* `--verbose` streams full Kiro output and prints the detailed terminal table.
* `--timeout N`, `--output-dir PATH`, and `--report PATH` change runtime or
  artifact settings.
* `--aws PATH` and `--kiro-cli PATH` select executables.
* `--from-data` validates the current schema-v4 `trials.json` and regenerates
  the report without Kiro or subprocess sessions. Older schemas are rejected;
  rerun the experiment to replace them.

Sessions run sequentially and can take several minutes.

## Interpreting results

The primary outcome is **corrected and reached a clean result**. It requires:

1. the agent observed a diagnostic;
2. it changed the request while keeping the same AWS service and operation;
   and
3. the changed request produced a clean validation or a successful request to
   the local endpoint.

All issue-producing cases remain in the denominator even when no diagnostic is
observed. The report separately shows diagnostic observation, correction
attempts, first-correction success, calls and time to clean, validation use,
and whether validation blocked an unresolved live request. `--validate-only`
use is a technique, not the success criterion.

The baseline and information-only conditions have the same neutral task
wording; they differ only in whether the flag is described. The guided
condition explicitly instructs the correction workflow and is therefore not a
neutral comparison. If all conditions reach 100% on the primary outcome, use
the execution-path and efficiency measures to understand differences; do not
claim that the conditions are equivalent.

## Reports and raw evidence

Generated Markdown reports are intentionally tracked:

* `scripts/cfn-validate-report.md` — validator-only run.
* `scripts/s3-agent-loop-report.md` — standalone one-pass run.
* `scripts/s3-agent-safety-report.md` — repeated experiment.

Disposable evidence is ignored by Git:

* `scripts/*-<condition>.txt` and matching `.jsonl` files;
* `scripts/s3-agent-safety-data/trials.json` and `manifest.json`;
* per-session transcripts and raw events;
* per-repetition results, one-pass reports under
  `scripts/s3-agent-safety-data/raw/`, and logs.

The aggregate report is a deterministic function of `trials.json` and
`manifest.json`. Read it with:

```text
less scripts/s3-agent-safety-report.md
```

## Verification and tests

There are no committed demo-specific unit-test modules in the current branch.
Use these executable checks:

```text
# Syntax and static checks
python3 -m py_compile \
  scripts/demo-cfn-validate \
  scripts/demo-s3-agent-loop \
  scripts/run-s3-agent-safety-experiment
python3 -m ruff check \
  scripts/demo-cfn-validate \
  scripts/demo-s3-agent-loop \
  scripts/run-s3-agent-safety-experiment

# Offline case discovery; does not launch Kiro
python3 scripts/demo-s3-agent-loop --list-cases

# Deterministic local integration check; no Kiro, credentials, or HTTP
python3 scripts/demo-cfn-validate

# Validate an existing dataset and regenerate its report without agents
python3 scripts/run-s3-agent-safety-experiment --from-data
```

For end-to-end agent verification, run the one-pass or repeated command. Both
fail on high-impact safety violations; the repeated runner also validates the
complete dataset before writing its report.

## Troubleshooting

* Run commands from the repository root so relative paths and profile copying
  resolve correctly.
* If Kiro cannot start, verify that it is installed and authenticated. The
  validator-only demo does not require Kiro.
* If `--from-data` reports an unsupported schema, rerun the experiment without
  `--from-data`.
* Use `--list-cases` or each command's `--help` before starting a long agent
  run.
