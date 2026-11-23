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

"""Page object for the confirmation shown when Save changes the 'Enforce member spend limits' switch.

Rendered by the Edit Project modal on /settings/administration/projects as a second dialog
above it. FE source of truth (codemie-ui):
  src/pages/settings/administration/projectsManagement/components/EnforcementConfirmation.tsx
  src/constants/projectEnforcement.ts (header and button copy)
The dialog is a PrimeReact Dialog, so its accessible name is its header text.
"""

import re

from playwright.sync_api import Locator, expect
from reportportal_client import step

from codemie_test_harness.tests.ui.pageobject.base_page import BasePage

CONFIRMATION_HEADER = re.compile(r"Turn (on|off) member spend limit enforcement\?")


class EnforcementConfirmationDialog(BasePage):
    """Confirm / Cancel dialog for switching member spend limit enforcement."""

    @property
    def dialog(self) -> Locator:
        """The enforcement confirmation dialog, told apart from Edit Project by its name."""
        return self.page.get_by_role("dialog", name=CONFIRMATION_HEADER)

    @property
    def confirm_button(self) -> Locator:
        """The 'Turn on enforcement' / 'Turn off enforcement' button."""
        return self.dialog.get_by_role(
            "button", name=re.compile(r"Turn (on|off) enforcement")
        )

    @property
    def cancel_button(self) -> Locator:
        """The Cancel button of the confirmation."""
        return self.dialog.get_by_role("button", name="Cancel", exact=True)

    @step
    def press_escape(self):
        """Press the Escape key, then let the browser render two frames so a dialog that the
        key closes is gone before any "still open" assertion runs."""
        self.page.keyboard.press("Escape")
        self.page.evaluate(
            "() => new Promise(resolve => requestAnimationFrame("
            "() => requestAnimationFrame(resolve)))"
        )
        return self

    @step
    def click_confirm_capturing_save(self, project_name: str):
        """Click the confirm button and wait until the browser has sent the project PATCH."""
        with self.page.expect_request(
            lambda r: r.method == "PATCH" and f"/v1/projects/{project_name}" in r.url,
            timeout=15000,
        ):
            self.confirm_button.click()
        return self

    @step
    def should_be_visible(self):
        """Verify the confirmation is open with Confirm and Cancel offered."""
        expect(self.dialog).to_be_visible()
        expect(self.confirm_button).to_be_visible()
        expect(self.cancel_button).to_be_visible()
        return self

    @step
    def should_be_pending(self):
        """Verify the confirmation is still open and its confirm button is disabled, which is
        how the UI shows that the confirmed save is in flight."""
        expect(self.dialog).to_be_visible()
        expect(self.confirm_button).to_be_disabled()
        return self

    @step
    def should_be_closed(self):
        """Verify the confirmation is gone."""
        expect(self.dialog).not_to_be_visible()
        return self
