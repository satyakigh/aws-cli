# cloudformation-validate diagnostic stimulus report

**Purpose.** This report characterizes the deterministic `cloudformation-validate` diagnostic *stimulus* produced by `scripts/demo-cfn-validate`. **No agent runs here** — it records only what the validator itself emits for a fixed set of AWS requests, so the agent-response demos can be read against a known stimulus. Every percentage below characterizes this deterministic stimulus case mix, **not** AI or agent behavior.

- Generated: 2026-08-25T15:56:02.364560-06:00
- AWS CLI: `/Volumes/workplace/external-tools/aws-cli/build/venv/bin/aws`
- Cases executed (24): `s3-create-valid`, `s3-create-invalid`, `sns-create-topic-valid`, `lambda-update-valid`, `lambda-update-invalid`, `read-only-list-buckets`, `read-only-describe-instances`, `data-plane-lambda-invoke`, `data-plane-sqs-send-message`, `dynamodb-delete-table`, `dynamodb-create-table-nested`, `ec2-create-sg-unmapped`, `cfn-create-stack-valid-body`, `cfn-create-stack-invalid-body`, `cloudcontrol-create-valid`, `cloudcontrol-create-invalid`, `cloudcontrol-unknown-type`, `cloudcontrol-update-patch`, `s3-create-acl-public-read`, `s3-create-grant-read-public`, `s3-put-bucket-policy-unmapped`, `cfn-s3-access-control-no-ownership`, `cfn-s3-access-control-with-ownership`, `cfn-s3-secure-public-access-block`

## Executive summary

Outcomes are derived solely from each case's exact process exit code; statuses and diagnostics are parsed solely from the validator output each run emitted. These percentages characterize the fixed, deterministic stimulus case mix exercised in this run — they are **not** a measure of any agent or AI behavior.

Outcome (by exit code) over 24 case(s):

- CLEAN: 75% (18/24)
- FINDINGS: 25% (6/24)
- ERROR: 0% (0/24)

Status (parsed from validator output) over 24 case(s):

- VALIDATED: 50% (12/24)
- SKIPPED: 50% (12/24)
- unknown: 0% (0/24)

## Diagnostics by severity

Across 24 case(s), 7 diagnostic(s) were parsed. **Cases** counts the cases with at least one diagnostic of that severity; **Diagnostics** counts every diagnostic of that severity.

| Severity | Cases | Diagnostics |
|---|---|---|
| FATAL | 4 | 4 |
| ERROR | 1 | 1 |
| WARN | 2 | 2 |

## Per-case results

| Case | Description | Command | Classification | Status | Diagnostics | Outcome | Exit |
|---|---|---|---|---|---|---|---|
| s3-create-valid | Valid S3 CreateBucket — synthesized, zero findings | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api create-bucket --bucket my-demo-bucket-2024` | CLOUD_FORMATION_CREATE | VALIDATED | none | CLEAN | 0 |
| s3-create-invalid | S3 CreateBucket with invalid bucket name — synthesized, pattern violation | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api create-bucket --bucket Invalid_Bucket` | CLOUD_FORMATION_CREATE | VALIDATED | 1 (1 FATAL) | FINDINGS | 252 |
| sns-create-topic-valid | Valid SNS CreateTopic — synthesized, zero findings | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 sns create-topic --name MyValidTopic` | CLOUD_FORMATION_CREATE | VALIDATED | none | CLEAN | 0 |
| lambda-update-valid | Valid Lambda UpdateFunctionConfiguration — synthesized update, zero findings | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 lambda update-function-configuration --function-name my-func --memory-size 256` | CLOUD_FORMATION_UPDATE | VALIDATED | none | CLEAN | 0 |
| lambda-update-invalid | Lambda UpdateFunctionConfiguration with MemorySize below minimum — synthesized update, constraint violation | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 lambda update-function-configuration --function-name my-func --memory-size 7` | CLOUD_FORMATION_UPDATE | VALIDATED | 1 (1 FATAL) | FINDINGS | 252 |
| read-only-list-buckets | Read-only ListBuckets — SKIPPED | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api list-buckets` | READ_ONLY | SKIPPED | none | CLEAN | 0 |
| read-only-describe-instances | Read-only EC2 DescribeInstances — SKIPPED | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 ec2 describe-instances` | READ_ONLY | SKIPPED | none | CLEAN | 0 |
| data-plane-lambda-invoke | Lambda Invoke — data-plane mutation, SKIPPED | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 lambda invoke --function-name my-func /dev/null` | DATA_PLANE_MUTATION | SKIPPED | none | CLEAN | 0 |
| data-plane-sqs-send-message | SQS SendMessage — data-plane mutation, SKIPPED | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 sqs send-message --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/Q --message-body hello` | DATA_PLANE_MUTATION | SKIPPED | none | CLEAN | 0 |
| dynamodb-delete-table | DynamoDB DeleteTable — catalog delete, SKIPPED, detects AWS::DynamoDB::Table | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 dynamodb delete-table --table-name DemoTable` | CLOUD_FORMATION_DELETE | SKIPPED | none | CLEAN | 0 |
| dynamodb-create-table-nested | DynamoDB CreateTable with nested structures — SKIPPED, unrepresentable nested parameter | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 dynamodb create-table --table-name DemoTable --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE --billing-mode PAY_PER_REQUEST` | CLOUD_FORMATION_CREATE | SKIPPED | none | CLEAN | 0 |
| ec2-create-sg-unmapped | EC2 CreateSecurityGroup — SKIPPED, unmapped Description parameter | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 ec2 create-security-group --group-name my-sg --description 'test sg'` | CLOUD_FORMATION_CREATE | SKIPPED | none | CLEAN | 0 |
| cfn-create-stack-valid-body | CloudFormation CreateStack with valid TemplateBody | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudformation create-stack --stack-name demo-stack --template-body '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}'` | CLOUD_FORMATION_CREATE | VALIDATED | none | CLEAN | 0 |
| cfn-create-stack-invalid-body | CloudFormation CreateStack with invalid TemplateBody — pattern violation on BucketName | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudformation create-stack --stack-name demo-stack --template-body '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"Bucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "INVALID_NAME"}}}}'` | CLOUD_FORMATION_CREATE | VALIDATED | 1 (1 FATAL) | FINDINGS | 252 |
| cloudcontrol-create-valid | Cloud Control CreateResource with valid DesiredState | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudcontrol create-resource --type-name AWS::SNS::Topic --desired-state '{"TopicName": "ValidTopic123"}'` | CLOUD_FORMATION_CREATE | VALIDATED | none | CLEAN | 0 |
| cloudcontrol-create-invalid | Cloud Control CreateResource with invalid DesiredState — pattern violation on BucketName | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudcontrol create-resource --type-name AWS::S3::Bucket --desired-state '{"BucketName": "INVALID_UPPER"}'` | CLOUD_FORMATION_CREATE | VALIDATED | 1 (1 FATAL) | FINDINGS | 252 |
| cloudcontrol-unknown-type | Cloud Control CreateResource with unknown type — SKIPPED, no known CloudFormation TypeName | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudcontrol create-resource --type-name AWS::Fake::Resource --desired-state '{"Name": "test"}'` | UNMAPPED_MUTATION | SKIPPED | none | CLEAN | 0 |
| cloudcontrol-update-patch | Cloud Control UpdateResource — SKIPPED, PatchDocument cannot be synthesized | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudcontrol update-resource --type-name AWS::SQS::Queue --identifier MyQueue --patch-document '[{"op": "replace", "path": "/VisibilityTimeout", "value": "60"}]'` | UNMAPPED_MUTATION | SKIPPED | none | CLEAN | 0 |
| s3-create-acl-public-read | S3 CreateBucket with ACL public-read — SKIPPED, ACL parameter has no property mapping | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api create-bucket --bucket acl-demo-bucket-2024 --acl public-read` | CLOUD_FORMATION_CREATE | SKIPPED | none | CLEAN | 0 |
| s3-create-grant-read-public | S3 CreateBucket with GrantRead to AllUsers — SKIPPED, GrantRead parameter has no property mapping | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api create-bucket --bucket grant-demo-bucket-2024 --grant-read uri=http://acs.amazonaws.com/groups/global/AllUsers` | CLOUD_FORMATION_CREATE | SKIPPED | none | CLEAN | 0 |
| s3-put-bucket-policy-unmapped | S3 PutBucketPolicy — SKIPPED, Policy parameter has no property mapping | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 s3api put-bucket-policy --bucket policy-demo-bucket-2024 --policy '{"Version": "2012-10-17", "Statement": [{"Sid": "AllowGetObject", "Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789012:root"}, "Action": "s3:GetObject", "Resource": "arn:aws:s3:::policy-demo-bucket-2024/*"}]}'` | CLOUD_FORMATION_CREATE | SKIPPED | none | CLEAN | 0 |
| cfn-s3-access-control-no-ownership | CloudFormation CreateStack with S3 AccessControl but no OwnershipControls — two findings | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudformation create-stack --stack-name access-control-stack --template-body '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"Bucket": {"Type": "AWS::S3::Bucket", "Properties": {"AccessControl": "PublicRead"}}}}'` | CLOUD_FORMATION_CREATE | VALIDATED | 2 (1 ERROR, 1 WARN) | FINDINGS | 252 |
| cfn-s3-access-control-with-ownership | CloudFormation CreateStack with S3 AccessControl and OwnershipControls ObjectWriter — one finding | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudformation create-stack --stack-name access-control-ownership-stack --template-body '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"Bucket": {"Type": "AWS::S3::Bucket", "Properties": {"AccessControl": "PublicRead", "OwnershipControls": {"Rules": [{"ObjectOwnership": "ObjectWriter"}]}}}}}'` | CLOUD_FORMATION_CREATE | VALIDATED | 1 (1 WARN) | FINDINGS | 252 |
| cfn-s3-secure-public-access-block | CloudFormation CreateStack with secure S3 Bucket PublicAccessBlockConfiguration and scoped BucketPolicy — zero findings | `aws --validate-only --region us-east-1 --endpoint-url http://127.0.0.1:1 cloudformation create-stack --stack-name secure-bucket-stack --template-body '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"SecureBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "secure-demo-bucket-2024", "PublicAccessBlockConfiguration": {"BlockPublicAcls": true, "BlockPublicPolicy": true, "IgnorePublicAcls": true, "RestrictPublicBuckets": true}}}, "BucketPolicy": {"Type": "AWS::S3::BucketPolicy", "Properties": {"Bucket": {"Ref": "SecureBucket"}, "PolicyDocument": {"Version": "2012-10-17", "Statement": [{"Sid": "AllowAccountGet", "Effect": "Allow", "Principal": {"AWS": {"Fn::Sub": "arn:aws:iam::${AWS::AccountId}:root"}}, "Action": "s3:GetObject", "Resource": {"Fn::Sub": "arn:aws:s3:::${SecureBucket}/*"}}]}}}}}'` | CLOUD_FORMATION_CREATE | VALIDATED | none | CLEAN | 0 |

## Severity meanings and method

Validation runs at the WARN threshold, so only these severities surface:

- **FATAL** — a structural deployment failure; the request or template cannot deploy as written.
- **ERROR** — a likely deployment failure or incorrect behavior.
- **WARN** — a security, deprecation, or otherwise risky-pattern finding.

Method: every case runs `aws --validate-only ...` in an isolated child environment — all inherited `AWS_*` variables removed, no credentials set (**credential-free**), IMDS and retries disabled, and the global and per-service endpoints pinned to an unroutable loopback endpoint. Because `--validate-only` always stops before transport (and before signing), the run is fully **offline** and makes **no HTTP call** to any AWS endpoint.

## Related generated reports

Each of the three reports is generated only by running its demo; none is hand-authored:

- `scripts/cfn-validate-report.md` — this validator-stimulus report, written by `scripts/demo-cfn-validate`.
- `scripts/s3-agent-loop-report.md` — the one-pass agent-behavior Markdown report, written by `scripts/demo-s3-agent-loop`.
- `scripts/s3-agent-safety-report.html` — the repeated-trials, self-contained HTML report, written by `scripts/run-s3-agent-safety-experiment`.

