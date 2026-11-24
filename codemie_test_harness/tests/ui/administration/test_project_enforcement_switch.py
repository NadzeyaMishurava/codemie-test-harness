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

"""UI + backend regression tests for the 'Enforce member spend limits' switch in Edit Project.

Covers: the switch for the Global Administrator, the Maintainer and the Project Admin of the
project; the explanation that precedes a change in each direction; storing a confirmed change
through the real backend and reading it back after reopening the project; Cancel; saving
without an enforcement change; a failed save followed by a retry; the audit record of the
acting user.

Escape on the confirmation lives in test_project_enforcement_confirmation.py. Role-based API
rejection lives in tests/projects/test_project_enforcement_permissions.py.

Accounts and projects come from the module-scoped `cli_ui_world` fixture
(tests/ui/administration/conftest.py). Every test first sets the stored state it needs through
the API as the harness admin; the projects are deleted with the fixture.
"""

import pytest
from hamcrest import assert_that, equal_to, has_length, is_

from codemie_test_harness.tests.test_data.project_activity_test_data import (
    ENFORCEMENT_EVENT,
)
from codemie_test_harness.tests.ui.pageobject.administration.enforcement_confirmation_dialog import (
    EnforcementConfirmationDialog,
)
from codemie_test_harness.tests.ui.pageobject.administration.project_details_page import (
    ProjectDetailsPage,
)
from codemie_test_harness.tests.ui.test_data.project_enforcement_test_data import (
    DESCRIPTION_SUFFIX,
    ENFORCEMENT_FIELD,
    ORIGINAL_DESCRIPTION,
)
from codemie_test_harness.tests.utils.activity_utils import ActivityUtils

pytestmark = [
    pytest.mark.ui,
    pytest.mark.project,
    pytest.mark.oss_standalone,
]

GLOBAL_ADMIN = pytest.param("cli_global_admin", id="global admin")
MAINTAINER = pytest.param("cli_maintainer", id="maintainer")
PROJECT_ADMIN = pytest.param("cli_project_admin", id="project admin")

STORED_OFF = pytest.param(False, id="off to on")
STORED_ON = pytest.param(True, id="on to off")

AS_ANY_ENFORCER = pytest.mark.parametrize(
    "acting_credentials", [GLOBAL_ADMIN, MAINTAINER, PROJECT_ADMIN], indirect=True
)
AS_GLOBAL_OR_PROJECT_ADMIN = pytest.mark.parametrize(
    "acting_credentials", [GLOBAL_ADMIN, PROJECT_ADMIN], indirect=True
)
AS_PROJECT_ADMIN = pytest.mark.parametrize(
    "acting_credentials", [PROJECT_ADMIN], indirect=True
)
AS_GLOBAL_ADMIN = pytest.mark.parametrize(
    "acting_credentials", [GLOBAL_ADMIN], indirect=True
)


def _enforcement(project_utils, project_name: str) -> bool:
    return getattr(project_utils.get_project_detail(project_name), ENFORCEMENT_FIELD)


def _prepare(project_utils, project_name: str, stored: bool):
    """Put the project into a known stored state: original description, given enforcement."""
    project_utils.update_project(project_name, description=ORIGINAL_DESCRIPTION)
    project_utils.set_enforce_member_spend_limits(project_name, stored)
    assert_that(
        _enforcement(project_utils, project_name),
        is_(stored),
        "precondition: the stored enforcement setting",
    )


@pytest.fixture
def trail_instance_id(cli_ui_world, project_utils) -> str:
    """The id the project's activity trail is addressed by; the test is skipped on a backend
    that does not provide the trail (the project detail carries no project_instance_id)."""
    instance_id = project_utils.get_project_detail(
        cli_ui_world.target
    ).project_instance_id
    if instance_id is None:
        pytest.skip(
            "this backend has no project activity trail (no project_instance_id)"
        )
    return str(instance_id)


# ── Confirmed change is stored and survives reopening ───────────────────────────────


@AS_ANY_ENFORCER
@pytest.mark.parametrize("stored", [STORED_OFF, STORED_ON])
def test_confirmed_enforcement_change_is_stored_and_survives_reopen(
    page, cli_ui_world, project_utils, stored
):
    """The switch is offered and enabled, the explanation matches the direction, nothing is
    stored until Confirm, and after Confirm the backend and a reopened Edit Project show the
    new value."""
    project = cli_ui_world.target
    _prepare(project_utils, project, stored)
    details = ProjectDetailsPage(page).navigate_to(project)
    modal = details.open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.should_have_enforcement_value(stored)
    modal.toggle_enforcement()
    modal.should_have_enforcement_value(not stored)
    modal.click_save_to_confirm_enforcement()

    confirmation.should_be_visible()
    confirmation.should_explain(turning_on=not stored)
    assert_that(
        _enforcement(project_utils, project),
        is_(stored),
        "nothing is stored before the user confirms",
    )

    confirmation.confirm()
    modal.should_show_project_updated_toast(project)
    confirmation.should_be_closed()
    assert_that(
        _enforcement(project_utils, project),
        is_(not stored),
        "the confirmed change is stored by the backend",
    )

    details.navigate_to(project)
    details.open_edit_project().should_have_enforcement_value(not stored)


# ── Audit: the acting user is recorded ─────────────────────────────────────────────


@AS_PROJECT_ADMIN
def test_project_admin_change_is_audited_with_the_acting_user(
    page,
    cli_ui_world,
    project_utils,
    maintainer_client,
    trail_instance_id,
    acting_credentials,
):
    """A change a project admin confirms in the UI leaves one enforcement event that names
    the new value and the project admin as actor."""
    project = cli_ui_world.target
    actor_id = acting_credentials[2]
    _prepare(project_utils, project, False)
    activity = ActivityUtils(maintainer_client)
    events_before = activity.list_all_project_events(
        trail_instance_id, event_type=[ENFORCEMENT_EVENT]
    )
    modal = ProjectDetailsPage(page).navigate_to(project).open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.toggle_enforcement()
    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()
    confirmation.confirm()
    modal.should_show_project_updated_toast(project)

    events = activity.list_all_project_events(
        trail_instance_id, event_type=[ENFORCEMENT_EVENT]
    )
    assert_that(
        events, has_length(len(events_before) + 1), "one enforcement event is recorded"
    )
    assert_that(
        events[0].attributes,
        equal_to(
            {
                "previous_enforce_member_spend_limits": False,
                "new_enforce_member_spend_limits": True,
            }
        ),
        "the event records the previous and the new value",
    )
    assert_that(events[0].actor_id, equal_to(actor_id), "the acting user is recorded")


# ── Cancel ─────────────────────────────────────────────────────────────────────────


@AS_GLOBAL_OR_PROJECT_ADMIN
@pytest.mark.parametrize("stored", [STORED_OFF, STORED_ON])
def test_cancel_stores_nothing_and_keeps_the_other_edits(
    page, cli_ui_world, project_utils, stored
):
    """Cancel closes only the explanation: the switch returns to its stored value, the form and
    the unrelated edit stay, nothing is stored; saving again then stores only the other edit
    and asks nothing."""
    project = cli_ui_world.target
    edited = ORIGINAL_DESCRIPTION + DESCRIPTION_SUFFIX
    _prepare(project_utils, project, stored)
    modal = ProjectDetailsPage(page).navigate_to(project).open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.append_to_edit_description(DESCRIPTION_SUFFIX)
    modal.toggle_enforcement()
    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()
    confirmation.cancel()

    confirmation.should_be_closed()
    modal.should_remain_open_for_editing()
    modal.should_have_enforcement_value(stored)
    modal.should_have_edit_description(edited)
    detail = project_utils.get_project_detail(project)
    assert_that(
        detail.description, equal_to(ORIGINAL_DESCRIPTION), "Cancel stores nothing"
    )
    assert_that(
        getattr(detail, ENFORCEMENT_FIELD), is_(stored), "Cancel keeps the setting"
    )

    request_body = modal.save_capturing_request(project)
    modal.should_show_project_updated_toast(project)
    confirmation.should_be_closed()
    assert_that(
        request_body[ENFORCEMENT_FIELD],
        is_(stored),
        "the retry resends the stored value, not the cancelled one",
    )
    detail = project_utils.get_project_detail(project)
    assert_that(detail.description, equal_to(edited), "the other edit is stored")
    assert_that(
        getattr(detail, ENFORCEMENT_FIELD), is_(stored), "the setting is unchanged"
    )


# ── Save without an enforcement change ─────────────────────────────────────────────


@AS_ANY_ENFORCER
def test_save_without_enforcement_change_asks_no_confirmation(
    page, cli_ui_world, project_utils
):
    """Saving another edit with the switch untouched shows no explanation and stores the edit
    without changing enforcement."""
    project = cli_ui_world.target
    edited = ORIGINAL_DESCRIPTION + DESCRIPTION_SUFFIX
    _prepare(project_utils, project, False)
    modal = ProjectDetailsPage(page).navigate_to(project).open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.append_to_edit_description(DESCRIPTION_SUFFIX)
    modal.click_save_to_confirm_enforcement()

    modal.should_show_project_updated_toast(project)
    confirmation.should_be_closed()
    detail = project_utils.get_project_detail(project)
    assert_that(detail.description, equal_to(edited), "the edit is stored")
    assert_that(getattr(detail, ENFORCEMENT_FIELD), is_(False), "enforcement unchanged")


@AS_GLOBAL_ADMIN
def test_toggling_back_to_the_stored_value_asks_no_confirmation(
    page, cli_ui_world, project_utils
):
    """A switch flipped twice is back at its stored value: saving asks nothing."""
    project = cli_ui_world.target
    edited = ORIGINAL_DESCRIPTION + DESCRIPTION_SUFFIX
    _prepare(project_utils, project, True)
    modal = ProjectDetailsPage(page).navigate_to(project).open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.toggle_enforcement()
    modal.toggle_enforcement()
    modal.should_have_enforcement_value(True)
    modal.append_to_edit_description(DESCRIPTION_SUFFIX)
    modal.click_save_to_confirm_enforcement()

    modal.should_show_project_updated_toast(project)
    confirmation.should_be_closed()
    detail = project_utils.get_project_detail(project)
    assert_that(detail.description, equal_to(edited), "the edit is stored")
    assert_that(getattr(detail, ENFORCEMENT_FIELD), is_(True), "enforcement unchanged")


# ── Failed save and retry ──────────────────────────────────────────────────────────


@AS_GLOBAL_ADMIN
def test_failed_confirmed_save_stores_nothing_and_retry_asks_again(
    page, cli_ui_world, project_utils
):
    """When the confirmed save fails (the browser's request is answered with HTTP 500 before
    it reaches the backend), nothing is stored, Edit Project stays open with the switch as the
    user set it and a new Save asks again; confirming then stores the change."""
    project = cli_ui_world.target
    _prepare(project_utils, project, False)
    modal = ProjectDetailsPage(page).navigate_to(project).open_edit_project()
    confirmation = EnforcementConfirmationDialog(page)

    modal.should_show_enforcement_switch()
    modal.toggle_enforcement()
    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()
    modal.fail_next_save_request(project)
    confirmation.confirm()

    confirmation.should_be_closed()
    modal.should_remain_open_for_editing()
    modal.should_have_enforcement_value(True)
    assert_that(
        _enforcement(project_utils, project),
        is_(False),
        "the failed save stores nothing",
    )

    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()
    confirmation.should_explain_turning_on()
    confirmation.confirm()
    modal.should_show_project_updated_toast(project)
    modal.stop_failing_save_requests()
    assert_that(
        _enforcement(project_utils, project), is_(True), "the retry stores the change"
    )
