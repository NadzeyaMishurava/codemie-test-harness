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

"""UI regression tests for the enforcement confirmation inside Edit Project.

Changing 'Enforce member spend limits' and pressing Save opens a confirmation above Edit Project.
Escape on that confirmation must behave like Cancel: close only the confirmation.

The project is created through the API; the browser performs the action under test; the
stored state is read back through the API.
"""

import pytest
from hamcrest import assert_that, equal_to, is_

from codemie_test_harness.tests.ui.pageobject.administration.enforcement_confirmation_dialog import (
    EnforcementConfirmationDialog,
)
from codemie_test_harness.tests.ui.pageobject.administration.project_management_page import (
    ProjectManagementPage,
)
from codemie_test_harness.tests.ui.pageobject.administration.project_modal_page import (
    ProjectModal,
)
from codemie_test_harness.tests.ui.test_data.project_enforcement_test_data import (
    DESCRIPTION_SUFFIX,
    ORIGINAL_DESCRIPTION,
)


# @case project_enforcement_escape_TC_001
@pytest.mark.project
@pytest.mark.budget
@pytest.mark.ui
def test_escape_on_enforcement_confirmation_keeps_edit_project_open(
    page, project, project_utils
):
    """Escape on the enforcement confirmation closes only the confirmation: Edit Project stays
    open with the unsaved description edit, the switch returns to its stored value and nothing
    is saved.
    """
    created = project(description=ORIGINAL_DESCRIPTION)
    edited_description = ORIGINAL_DESCRIPTION + DESCRIPTION_SUFFIX
    stored_enforcement = project_utils.get_project_detail(
        created.name
    ).enforce_member_spend_limits

    management_page = ProjectManagementPage(page)
    modal = ProjectModal(page)
    confirmation = EnforcementConfirmationDialog(page)

    management_page.navigate_to()
    management_page.click_edit_project(created.name)
    modal.should_show_enforcement_switch()
    modal.should_have_enforcement_value(stored_enforcement)
    modal.should_have_edit_description(ORIGINAL_DESCRIPTION)

    modal.append_to_edit_description(DESCRIPTION_SUFFIX)
    modal.toggle_enforcement()
    modal.should_have_enforcement_value(not stored_enforcement)

    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()
    modal.should_remain_open_for_editing()

    confirmation.press_escape()

    confirmation.should_be_closed()
    modal.should_remain_open_for_editing()
    modal.should_have_edit_description(edited_description)
    modal.should_have_enforcement_value(stored_enforcement)

    detail = project_utils.get_project_detail(created.name)
    assert_that(
        detail.description,
        equal_to(ORIGINAL_DESCRIPTION),
        "Escape must not save the edited description",
    )
    assert_that(
        detail.enforce_member_spend_limits,
        is_(stored_enforcement),
        "Escape must not change the stored enforcement setting",
    )


# @case project_enforcement_escape_TC_002
@pytest.mark.project
@pytest.mark.budget
@pytest.mark.ui
def test_escape_while_enforcement_save_is_pending_keeps_edit_project_open(
    page, project, project_utils
):
    """Escape while the confirmed save is still in flight changes nothing: Edit Project and the
    confirmation stay open with the user's edits, and once the real backend answers the save
    stores both the description and the enforcement setting.

    The save request is held in the browser and then sent unchanged to the backend, so the
    pending state lasts exactly as long as the test needs.
    """
    created = project(description=ORIGINAL_DESCRIPTION)
    edited_description = ORIGINAL_DESCRIPTION + DESCRIPTION_SUFFIX
    stored_enforcement = project_utils.get_project_detail(
        created.name
    ).enforce_member_spend_limits

    management_page = ProjectManagementPage(page)
    modal = ProjectModal(page)
    confirmation = EnforcementConfirmationDialog(page)

    management_page.navigate_to()
    management_page.click_edit_project(created.name)
    modal.should_show_enforcement_switch()
    modal.should_have_enforcement_value(stored_enforcement)

    modal.append_to_edit_description(DESCRIPTION_SUFFIX)
    modal.toggle_enforcement()
    modal.click_save_to_confirm_enforcement()
    confirmation.should_be_visible()

    modal.hold_save_requests(created.name)
    confirmation.click_confirm_capturing_save(created.name)
    confirmation.should_be_pending()

    confirmation.press_escape()

    modal.should_remain_open_for_editing()
    confirmation.should_be_pending()
    modal.should_have_edit_description(edited_description)
    modal.should_have_enforcement_value(not stored_enforcement)

    modal.release_held_save_requests()

    modal.should_show_project_updated_toast(created.name)
    detail = project_utils.get_project_detail(created.name)
    assert_that(
        detail.description,
        equal_to(edited_description),
        "The confirmed save must store the edited description",
    )
    assert_that(
        detail.enforce_member_spend_limits,
        is_(not stored_enforcement),
        "The confirmed save must store the new enforcement setting",
    )
