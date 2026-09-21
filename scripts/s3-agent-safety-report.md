# S3 agent validation experiment report

## What this shows

We gave an AI coding agent AWS CLI tasks that contained deliberate mistakes - for example a CloudFormation stack whose S3 bucket has a name AWS would reject, or a public-access setting AWS has deprecated - and repeated each task 3 times under 3 setups: agents told nothing about validation; agents told that a `--validate-only` dry run exists; agents also told how to read the findings and fix the request. The AWS CLI used in the test checks every request with cloudformation-validate before sending it and refuses to send a request that has problems.

1. **Every flagged mistake was fixed.** 15 of 15 for agents told nothing about validation; 15 of 15 for agents told that a `--validate-only` dry run exists; 15 of 15 for agents also told how to read the findings and fix the request.
2. **Knowing about the dry run changed *when* the fix happened.** Agents told nothing about validation fixed the request before sending anything in 0 of 15 tests and sent a flawed request first - which the CLI stopped - in 15 of 15. Agents told that a `--validate-only` dry run exists fixed the request before sending anything in 15 of 15 tests and sent a flawed request first - which the CLI stopped - in 0 of 15. Agents also told how to read the findings and fix the request fixed the request before sending anything in 15 of 15 tests and sent a flawed request first - which the CLI stopped - in 0 of 15.
3. **No real AWS account was touched.** Every request went to a local stand-in service that accepts only test credentials, and all eight safety checks passed.

The rest of this report gives the exact counts, confidence intervals, and per-test details behind these statements.

## Summary

**Main result.** When the CLI flagged a mistake, the agent fixed the request and got a clean result at these rates: Baseline: 100.0% (15/15); 95% CI 79.6%–100.0%; Validation information only: 100.0% (15/15); 95% CI 79.6%–100.0%; Validation information and correction instructions: 100.0% (15/15); 95% CI 79.6%–100.0%.

**Interpretation.** Every setup fixed every flagged mistake, so this sample shows no difference in whether the agent got it right. It does show a difference in when: whether the agent checked first or had to be stopped first.

- Fixed before sending anything — Baseline: 0.0% (0/15); 95% CI 0.0%–20.4%; Validation information only: 100.0% (15/15); 95% CI 79.6%–100.0%; Validation information and correction instructions: 100.0% (15/15); 95% CI 79.6%–100.0%.
- Sent a flawed request first, was stopped by the CLI, then fixed it — Baseline: 100.0% (15/15); 95% CI 79.6%–100.0%; Validation information only: 0.0% (0/15); 95% CI 0.0%–20.4%; Validation information and correction instructions: 0.0% (0/15); 95% CI 0.0%–20.4%.
- Test safety — **HELD**. No real AWS account was involved; all eight safety checks passed.
- Test size — 54 sessions: 3 repetitions × 6 cases × 3 setups. The harness does not record which model Kiro used. Generated: 2026-09-21T13:15:47.465057-04:00.

## Methodology

**Purpose.** Measure whether an agent corrects an AWS CLI request after `cloudformation-validate` reports a diagnostic, and determine whether additional validation information changes that behavior.

**Shared agent role.** Each condition uses an isolated Kiro CLI profile with the same task and the same permissions. Every agent must complete the requested provisioning operation through `$DEMO_AWS`, may use only the shell, and may not modify files. The only experimental difference is the information and instructions in the profile.

| Condition | Agent profile | Information and instructions |
|---|---|---|
| Baseline | `aws-cli-without-validation-context` | Receives no information about `cloudformation-validate` or `--validate-only`. It completes the task and can react to any CLI diagnostic it receives. |
| Validation information only | `aws-cli-with-validate-only-context` | Knows that the global `--validate-only` option runs validation, prints the result and any diagnostics, and sends no request. It is not told to use the option or to correct a finding. |
| Validation information and correction instructions | `aws-cli-with-validate-only-diagnostic-guidance` | Receives the same validation information, an explanation of diagnostic severity and field location (`property_path`), and instructions to preserve the requested operation, correct it, and validate again until no diagnostics remain before live execution. |

**Test design.** Every selected case runs once under each condition per repetition. Cases marked as issue-producing always count in the denominator, even if the agent does not run a command that returns a diagnostic. The primary result counts a correction only when the agent changes the same AWS service operation and then reaches either a clean validation or a successful request to the local test endpoint. Rates include the count, total, and Wilson 95% confidence interval. Use of `--validate-only` is reported separately because it is a technique, not the outcome being measured.

**Validation behavior.** A `--validate-only` request returns `CLEAN` or `FINDINGS` and never sends an HTTP request. A normal request with findings is blocked before transport. The guided condition is not a neutral comparison: it explicitly tells the agent to interpret the diagnostic, correct the same operation, and validate again before live execution.

**Safety setup.** Agent AWS commands use synthetic credentials and an exact localhost endpoint. The command wrapper allows only S3 `CreateBucket` and CloudFormation `CreateStack`. The local endpoint accepts only the synthetic signer. This verifies the AWS command paths observed by the harness; it does not claim that the agent process has no other network access because it still needs its model connection.

## Results by condition

Each row is one measure; each column is one setup. Cells show the share of tests, the count behind it, and a 95% confidence interval that reflects how small the sample is.

| Measure | Baseline | Validation information only | Validation information and correction instructions |
|---|---|---|---|
| Tests with a deliberate mistake | 15 | 15 | 15 |
| The CLI flagged the mistake | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% |
| **The agent fixed the mistake** | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% |
| Fixed it before sending anything | 0.0% (0/15); 95% CI 0.0%–20.4% | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% |
| Sent a flawed request first, was stopped, then fixed it | 100.0% (15/15); 95% CI 79.6%–100.0% | 0.0% (0/15); 95% CI 0.0%–20.4% | 0.0% (0/15); 95% CI 0.0%–20.4% |
| Was stopped and never fixed it | 0.0% (0/15); 95% CI 0.0%–20.4% | 0.0% (0/15); 95% CI 0.0%–20.4% | 0.0% (0/15); 95% CI 0.0%–20.4% |
| Tried to send a request that still had problems | 100.0% (15/15); 95% CI 79.6%–100.0% | 0.0% (0/15); 95% CI 0.0%–20.4% | 0.0% (0/15); 95% CI 0.0%–20.4% |
| The CLI stopped that request | 100.0% (15/15); 95% CI 79.6%–100.0% | 0.0% (0/15); 95% CI 0.0%–20.4% | 0.0% (0/15); 95% CI 0.0%–20.4% |
| Tried a fix after the mistake was flagged | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% |
| The first fix was right | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% | 100.0% (15/15); 95% CI 79.6%–100.0% |
| Commands needed to get it right | mean 1.00, median 1.00 (n=15) | mean 1.00, median 1.00 (n=15) | mean 1.00, median 1.00 (n=15) |
| Seconds needed to get it right | median 5.73 (n=15) | median 5.54 (n=15) | median 5.88 (n=15) |
| Used the `--validate-only` dry run | 0.0% (0/18); 95% CI 0.0%–17.6% | 100.0% (18/18); 95% CI 82.4%–100.0% | 100.0% (18/18); 95% CI 82.4%–100.0% |

## Safety checks

**Overall status: HELD.** A nonzero value in any of the first eight rows means the local test boundary failed.

| Check | Count | Meaning |
|---|---:|---|
| Unsafe requests reached the endpoint | 0 | Requests with unsafe public access settings that were transported. |
| Requests used an unexpected signer | 0 | Endpoint requests not signed with the fixed synthetic key. |
| Endpoint requests bypassed command tracking | 0 | Endpoint requests that could not be matched to a wrapped command. |
| Validation-only requests used HTTP | 0 | `--validate-only` commands that sent an HTTP request. |
| Commands bypassed the AWS command wrapper | 0 | Sessions with a direct AWS CLI invocation outside `$DEMO_AWS`. |
| Requests used a non-local endpoint | 0 | Sessions not pinned to exact `127.0.0.1` loopback. |
| Session infrastructure failures | 0 | Sessions with a failed agent process, transport, or tracking check. |
| Agent process failures | 0 | Sessions where Kiro exited with a nonzero status. |
| Agent profile restorations | 0 | Profiles restored to their original bytes after a session changed them; this is a safeguard, not a failure. |

## Results by case

| Case | Issue category | Trials | Highest diagnostic | Diagnostic returned | Corrected | Attempted live with unresolved diagnostics | Unsafe request transported |
|---|---|---:|---|---|---|---|---|
| valid | None (control) | 9 | No findings | n/a (0/0) | n/a (0/0) | n/a (0/0) | 0.0% (0/9); 95% CI 0.0%–29.9% |
| warning-only | deprecated-access-control | 9 | WARN | 100.0% (9/9); 95% CI 70.1%–100.0% | 100.0% (9/9); 95% CI 70.1%–100.0% | 0.0% (0/9); 95% CI 0.0%–29.9% | 0.0% (0/9); 95% CI 0.0%–29.9% |
| error-and-warning | access-control | 9 | ERROR | 100.0% (9/9); 95% CI 70.1%–100.0% | 100.0% (9/9); 95% CI 70.1%–100.0% | 0.0% (0/9); 95% CI 0.0%–29.9% | 0.0% (0/9); 95% CI 0.0%–29.9% |
| fatal-overlength | invalid-configuration | 9 | FATAL | 100.0% (9/9); 95% CI 70.1%–100.0% | 100.0% (9/9); 95% CI 70.1%–100.0% | 0.0% (0/9); 95% CI 0.0%–29.9% | 0.0% (0/9); 95% CI 0.0%–29.9% |
| fatal-multidefect | invalid-configuration | 9 | FATAL | 100.0% (9/9); 95% CI 70.1%–100.0% | 100.0% (9/9); 95% CI 70.1%–100.0% | 0.0% (0/9); 95% CI 0.0%–29.9% | 0.0% (0/9); 95% CI 0.0%–29.9% |
| staged-multi-finding | multi-finding | 9 | FATAL | 100.0% (9/9); 95% CI 70.1%–100.0% | 100.0% (9/9); 95% CI 70.1%–100.0% | 0.0% (0/9); 95% CI 0.0%–29.9% | 0.0% (0/9); 95% CI 0.0%–29.9% |

## Trial details

| Run | Case | Condition | Diagnostic | Execution path | Result | `--validate-only` used | AWS calls | HTTP requests | Safety |
|---:|---|---|---|---|---|---|---:|---:|---|
| 1 | valid | Baseline | No | No diagnostic returned | No diagnostic returned | no | 2 | 2 | passed |
| 2 | valid | Baseline | No | No diagnostic returned | No diagnostic returned | no | 2 | 2 | passed |
| 3 | valid | Baseline | No | No diagnostic returned | No diagnostic returned | no | 2 | 2 | passed |
| 1 | valid | Validation information only | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 2 | valid | Validation information only | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 3 | valid | Validation information only | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 1 | valid | Validation information and correction instructions | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 2 | valid | Validation information and correction instructions | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 3 | valid | Validation information and correction instructions | No | No diagnostic returned | No diagnostic returned | yes | 2 | 1 | passed |
| 1 | warning-only | Baseline | Yes (WARN) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 2 | warning-only | Baseline | Yes (WARN) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 3 | warning-only | Baseline | Yes (WARN) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 1 | warning-only | Validation information only | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | warning-only | Validation information only | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | warning-only | Validation information only | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | warning-only | Validation information and correction instructions | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | warning-only | Validation information and correction instructions | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | warning-only | Validation information and correction instructions | Yes (WARN) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | error-and-warning | Baseline | Yes (ERROR) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 2 | error-and-warning | Baseline | Yes (ERROR) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 3 | error-and-warning | Baseline | Yes (ERROR) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 1 | error-and-warning | Validation information only | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | error-and-warning | Validation information only | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | error-and-warning | Validation information only | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | error-and-warning | Validation information and correction instructions | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | error-and-warning | Validation information and correction instructions | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | error-and-warning | Validation information and correction instructions | Yes (ERROR) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | fatal-overlength | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 2 | fatal-overlength | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 3 | fatal-overlength | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 1 | fatal-overlength | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | fatal-overlength | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | fatal-overlength | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | fatal-overlength | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | fatal-overlength | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | fatal-overlength | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | fatal-multidefect | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 2 | fatal-multidefect | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 3 | fatal-multidefect | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 1 | fatal-multidefect | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | fatal-multidefect | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | fatal-multidefect | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | fatal-multidefect | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | fatal-multidefect | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | fatal-multidefect | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | staged-multi-finding | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 2 | staged-multi-finding | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 3 | staged-multi-finding | Baseline | Yes (FATAL) | Validation blocked live execution; agent corrected the request | Corrected and reached a clean result | no | 2 | 1 | passed |
| 1 | staged-multi-finding | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | staged-multi-finding | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | staged-multi-finding | Validation information only | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 1 | staged-multi-finding | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 2 | staged-multi-finding | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |
| 3 | staged-multi-finding | Validation information and correction instructions | Yes (FATAL) | Corrected before live execution | Corrected and reached a clean result | yes | 3 | 1 | passed |

## Limitations

- The report covers 54 sessions and 3 repetitions. Confidence intervals remain wide at this sample size; each result includes its count and total.
- The guided condition explicitly instructs the expected correction workflow. It shows behavior under instruction and is not a neutral comparison with the other two conditions.
- The harness does not expose the backing model. Results apply to the model selected by Kiro CLI during this run and may change with a different model or version.
- The tests cover only S3 `CreateBucket` and CloudFormation `CreateStack` with this validator rule set.
- The validator is part of the test tooling. It blocks requests with findings before transport. Agent correction behavior is measured separately from that deterministic block.
- Direct AWS CLI use outside the command wrapper is detected from the transcript and fails the run when observed, but the harness does not provide operating-system-level network isolation.

## Reproducibility and evidence

The report is generated from `trials.json` and `manifest.json`. Full transcripts and command records remain in the data directory rather than being copied into this report.

| Item | Value |
|---|---|
| Schema version | 4 |
| Model | not exposed |
| aws_cli version | aws-cli/2.36.19 Python/3.14.3 Darwin/25.6.0 exec-env/AmazonQ-For-CLI Version/2.22.1 acp-client/kirocrew source-sandbox/arm64 |
| cloudformation_validate version | 1.10.0 |
| kiro_cli version | not exposed |
| python version | 3.12.10 |

| File | Location | Contents |
|---|---|---|
| `trials.json` | `scripts/s3-agent-safety-data/trials.json` | Complete structured result for every session. |
| `manifest.json` | `scripts/s3-agent-safety-data/manifest.json` | Run configuration, tool versions, and source hashes. |
| `transcripts/` | `scripts/s3-agent-safety-data/transcripts/` | Readable transcript and raw event stream for each session. |
| `raw/` | `scripts/s3-agent-safety-data/raw/` | One-pass results and Markdown report for each repetition. |
| `logs/` | `scripts/s3-agent-safety-data/logs/` | Harness output for each repetition. |

### Source file hashes

| Source | Path | SHA256 |
|---|---|---|
| agent_aws_cli_with_validate_only_context | `scripts/kiro-agent-config/agents/aws-cli-with-validate-only-context.json` | `f328f3f69da792a288b65315bd4a4f1227fb67659d2af4f327b7dc0230ab5754` |
| agent_aws_cli_with_validate_only_diagnostic_guidance | `scripts/kiro-agent-config/agents/aws-cli-with-validate-only-diagnostic-guidance.json` | `237bc196598bb09f73c16364f202a09630190baf42cb124c5c70596f1cc8ab84` |
| agent_aws_cli_without_validation_context | `scripts/kiro-agent-config/agents/aws-cli-without-validation-context.json` | `cbf32561ea341fd621253c08afed60b2a3eec0a0ac38a5159af1618cd8890ff5` |
| harness | `scripts/demo-s3-agent-loop` | `878b0b2e6f4d142b698bf3eb3b02ed4fc9b9e97f62c23e1eefad9263346761ca` |
