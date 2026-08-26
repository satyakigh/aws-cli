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
"""CloudFormation validation hook registration."""

from awscli.customizations.cfnvalidate.hook import CfnValidateHook


def register_cfn_validate(event_handlers):
    hook = CfnValidateHook.instance()
    event_handlers.register(
        'building-top-level-params',
        hook.add_validation_params,
        unique_id='cfn-validate-params',
    )
    event_handlers.register(
        'session-initialized',
        hook.capture_session,
        unique_id='cfn-validate-session',
    )
    event_handlers.register(
        'provide-client-params',
        hook,
        unique_id='cfn-validate-hook',
    )
