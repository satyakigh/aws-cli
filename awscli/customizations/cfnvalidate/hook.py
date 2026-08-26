# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""Fail-closed CloudFormation validation hook."""

import functools
import json
import sys

from awscli.arguments import CustomArgument
from awscli.constants import PARAM_VALIDATION_ERROR_RC
from awscli.customizations.exceptions import (
    ConfigurationError,
    ParamValidationError,
)

# The single global flag that selects the fail-closed validation-only mode.
# When it is supplied the CLI runs cloudformation-validate on the request,
# renders the status, diagnostics, and a CLEAN/FINDINGS outcome, and always
# exits before transport: a clean or skipped request exits 0, findings exit
# nonzero.
VALIDATE_ONLY_FLAG = 'validate-only'
# Process return code used when a validation-only request has findings. The
# findings are a client-side validation failure, so this is the AWS CLI's
# canonical parameter-validation return code (252): the hook raises
# ParamValidationError and the standard ParamValidationErrorsHandler maps it
# to this code. It is nonzero so callers and scripts can tell CLEAN from
# FINDINGS by exit status alone; a clean or skipped validation-only request
# exits 0. It is deliberately not the reserved CLIENT_ERROR_RC (254).
VALIDATION_FINDINGS_RC = PARAM_VALIDATION_ERROR_RC


@functools.lru_cache(maxsize=1)
def _get_engine():
    """Construct or reuse a single RegoEngine instance."""
    try:
        from cloudformation_validate import (
            RegoEngine,
        )

        return RegoEngine()
    except Exception as exc:
        raise ConfigurationError(
            f'cloudformation-validate binding unavailable: {exc}'
        ) from exc


class CfnValidateHook:
    """Fail-closed validation interceptor."""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._validate_only = False

    def add_validation_params(self, session, argument_table, **kwargs):
        """Register the global ``--validate-only`` flag.

        This is the sole public hook surface. It registers only
        ``--validate-only``: when supplied, the CLI runs
        cloudformation-validate on the request and exits before transport,
        rendering the status, diagnostics, and a CLEAN/FINDINGS outcome.
        """
        argument_table['validate-only'] = CustomArgument(
            'validate-only',
            help_text=(
                'Validate the request with cloudformation-validate '
                'and exit without sending it to AWS. Always prevents '
                'API execution; a request with findings exits nonzero.'
            ),
            action='store_true',
            dest='cfn_validate_only',
            default=False,
        )

    def capture_session(self, session, parsed_args, **kwargs):
        self._validate_only = bool(
            getattr(parsed_args, 'cfn_validate_only', False)
        )

    @property
    def validation_only(self):
        """True when ``--validate-only`` selected the validation-only mode."""
        return self._validate_only

    def __call__(self, params, model, context, **kwargs):
        service_model = getattr(model, 'service_model', None)
        service_name = (
            getattr(service_model, 'service_name', None)
            or getattr(service_model, 'endpoint_prefix', None)
            or getattr(service_model, 'signing_name', None)
            or ''
        )
        service_prefix = (
            getattr(service_model, 'signing_name', None)
            or getattr(service_model, 'endpoint_prefix', None)
            or service_name
        )
        operation_name = getattr(model, 'name', '') or ''
        http = getattr(model, 'http', None)
        http_method = http.get('method') if isinstance(http, dict) else None
        operation_model = getattr(model, '_operation_model', None)
        is_read_only = (
            operation_model.get('readonly')
            if isinstance(operation_model, dict)
            and isinstance(operation_model.get('readonly'), bool)
            else None
        )

        try:
            result = self._validate(
                service_name=service_name,
                service_prefix=service_prefix,
                operation_name=operation_name,
                http_method=http_method,
                is_read_only=is_read_only,
                parameters=params,
            )
        except (ConfigurationError, ParamValidationError):
            raise
        except Exception as exc:
            raise ConfigurationError(
                f'cloudformation-validate hook failed: {exc}'
            ) from exc

        status = result.status.name
        report = result.report
        diagnostics = list(report.diagnostics) if report else []

        if self.validation_only:
            _render_validation_result(result, diagnostics)
            # A validation-only request never transports. Findings are a
            # client-side validation failure, so after rendering the FINDINGS
            # block raise ParamValidationError: the standard
            # ParamValidationErrorsHandler maps it to VALIDATION_FINDINGS_RC
            # (252). A clean or skipped request raises SystemExit(0), which
            # CLIDriver.main returns directly. The driver only preserves a
            # zero SystemExit code — a nonzero SystemExit is not mapped to a
            # process RC and would leak out as exit 0 — so findings must not
            # exit via SystemExit.
            if diagnostics:
                raise ParamValidationError(
                    f'cloudformation-validate: {len(diagnostics)} finding(s) '
                    f'blocked transport — request not sent'
                )
            raise SystemExit(0)

        if status == 'SKIPPED':
            return None

        if diagnostics:
            _render_diagnostics(diagnostics)
            raise ParamValidationError(
                f'cloudformation-validate: {len(diagnostics)} blocking '
                f'finding(s) — request not sent'
            )

        return None

    def _validate(
        self,
        service_name,
        service_prefix,
        operation_name,
        http_method,
        is_read_only,
        parameters,
    ):
        """Run validation and return the full result object."""
        from cloudformation_validate import (
            AwsApiRequest,
            Severity,
            ValidateConfig,
        )

        engine = _get_engine()
        request = AwsApiRequest(
            service_name=service_name,
            operation_name=operation_name,
            parameters=parameters,
            service_prefix=service_prefix,
            http_method=http_method,
            is_read_only=is_read_only,
        )
        return engine.validate_aws_api_request(
            request, ValidateConfig(severity_level=Severity.WARN)
        )


def _render_validation_result(result, diagnostics, stream=None):
    """Render rich validation-only output to stderr.

    The rendered block always ends with an explicit ``outcome:`` line:
    ``FINDINGS`` when any diagnostic is present, otherwise ``CLEAN`` (which
    also covers a SKIPPED request that was not validated).
    """
    out = stream if stream is not None else sys.stderr
    label = VALIDATE_ONLY_FLAG

    out.write(f'[cloudformation-validate] --- {label} result ---\n')
    out.write(
        f'[cloudformation-validate] classification: '
        f'{result.operation_kind.name}\n'
    )
    out.write(f'[cloudformation-validate] status: {result.status.name}\n')

    template_source = result.template_source
    out.write(
        f'[cloudformation-validate] template_source: '
        f'{template_source.name if template_source is not None else "none"}\n'
    )

    resource_types = result.resource_types
    out.write(
        f'[cloudformation-validate] detected_resources: '
        f'{", ".join(resource_types) if resource_types else "none"}\n'
    )

    out.write(f'[cloudformation-validate] reason: {result.reason}\n')

    # Access result.template directly so a stale/mismatched binding
    # raises AttributeError immediately rather than silently hiding.
    template_bytes = result.template
    if template_bytes is not None:
        out.write('[cloudformation-validate] modeled_template:\n')
        _render_template_bytes(template_bytes, out)
    else:
        out.write('[cloudformation-validate] modeled_template: none\n')

    if diagnostics:
        out.write(
            f'[cloudformation-validate] diagnostics: '
            f'{len(diagnostics)} finding(s)\n'
        )
        for d in diagnostics:
            path = d.property_path if d.property_path else 'none'
            out.write(
                f'[cloudformation-validate]   {d.severity.name}: '
                f'{d.message} [property_path: {path}]\n'
            )
    else:
        out.write('[cloudformation-validate] diagnostics: none\n')

    outcome = 'FINDINGS' if diagnostics else 'CLEAN'
    out.write(f'[cloudformation-validate] outcome: {outcome}\n')
    out.write(f'[cloudformation-validate] --- end {label} ---\n')


def _render_template_bytes(template_bytes, out):
    """Pretty-print template bytes as indented JSON or lossless text."""
    if isinstance(template_bytes, (bytes, bytearray)):
        text = bytes(template_bytes).decode('utf-8', errors='backslashreplace')
    else:
        raise TypeError(
            f'unexpected template type: {type(template_bytes).__name__}'
        )
    try:
        parsed = json.loads(text)
        formatted = json.dumps(parsed, indent=2, sort_keys=True)
    except json.JSONDecodeError:
        formatted = text
    for line in formatted.splitlines():
        out.write(f'[cloudformation-validate]   {line}\n')


def _render_diagnostics(diagnostics, stream=None):
    """Write findings to stderr."""
    if not diagnostics:
        return
    out = stream if stream is not None else sys.stderr
    out.write('[cloudformation-validate] validation findings:\n')
    for d in diagnostics:
        path = (
            f' ({d.property_path})'
            if getattr(d, 'property_path', None)
            else ''
        )
        out.write(
            f'[cloudformation-validate]   {d.severity.name}: '
            f'{d.message}{path}\n'
        )
    count = len(diagnostics)
    label = 'finding' if count == 1 else 'findings'
    out.write(f'[cloudformation-validate] {count} {label}\n')
