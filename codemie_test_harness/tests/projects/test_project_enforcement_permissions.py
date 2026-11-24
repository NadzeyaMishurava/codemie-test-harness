# Copyright 2026 EPAM Systems, Inc. (“EPAM”)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Who may change 'enforce_member_spend_limits' through the API.

The Project Admin of a project may change it (the Edit Project screen relies on that); a plain
member of the project and the admin of a different project may not: the call is rejected with 403 and
the stored value stays as it was. Needs a stand with real roles (not ENV=local, where every
user is a global admin).
"""

import pytest
from hamcrest import assert_that, equal_to, is_
from requests import HTTPError

from codemie_test_harness.tests.utils.client_factory import get_client

pytestmark = [pytest.mark.api, pytest.mark.project]


@pytest.fixture
def enforcement_world(
    default_project_member, project_admin_user, second_platform_user, user_utils
):
    """A project (`target`) and four callers: its admin, its plain member, and the admin of a
    different project; every client logged in after its role was assigned."""
    other_project_admin = second_platform_user
    user_utils.assign_user_to_project(
        other_project_admin.user_id,
        default_project_member.project_b,
        is_project_admin=True,
    )
    return {
        "target": default_project_member.project_a,
        "project_admin": get_client(
            username=project_admin_user.email, password=project_admin_user.password
        ),
        "member": default_project_member.client,
        "other_project_admin": get_client(
            username=other_project_admin.email, password=other_project_admin.password
        ),
    }


def _stored(project_utils, project_name):
    return project_utils.get_project_detail(project_name).enforce_member_spend_limits


@pytest.mark.parametrize("new_value", [True, False], ids=["turn on", "turn off"])
def test_project_admin_changes_enforcement_through_api(
    enforcement_world, project_utils, new_value
):
    target = enforcement_world["target"]
    project_utils.set_enforce_member_spend_limits(target, not new_value)

    response = enforcement_world["project_admin"].projects.update_project(
        project_name=target, enforce_member_spend_limits=new_value
    )

    assert_that(response.enforce_member_spend_limits, is_(new_value), "update response")
    assert_that(_stored(project_utils, target), is_(new_value), "stored value")


@pytest.mark.parametrize("caller", ["member", "other_project_admin"])
@pytest.mark.parametrize("new_value", [True, False], ids=["turn on", "turn off"])
def test_caller_without_rights_cannot_change_enforcement_through_api(
    enforcement_world, project_utils, caller, new_value
):
    target = enforcement_world["target"]
    project_utils.set_enforce_member_spend_limits(target, not new_value)

    with pytest.raises(HTTPError) as rejected:
        enforcement_world[caller].projects.update_project(
            project_name=target, enforce_member_spend_limits=new_value
        )

    assert_that(
        rejected.value.response.status_code,
        equal_to(403),
        "the change is rejected with a permission error",
    )
    assert_that(
        _stored(project_utils, target), is_(not new_value), "nothing was changed"
    )
