from django.urls import reverse
from temba.tests.base import TembaTest


class UserAuthTest(TembaTest):

    # Auth is handled by allauth, only test things we override in any way
    def test_signup(self):
        signup_url = reverse("account_signup")
        success_url = reverse("orgs.org_choose")

        response = self.client.get(signup_url)
        self.assertEqual(200, response.status_code)

        # bad inputs
        response = self.client.post(signup_url, {"email": "invalid"})
        self.assertEqual(200, response.status_code)
        form = response.context.get("form")
        self.assertFormError(form, "email", "Enter a valid email address.")
        self.assertFormError(form, "first_name", "This field is required.")
        self.assertFormError(form, "last_name", "This field is required.")
        self.assertFormError(form, "workspace", "This field is required.")

        # test valid signup
        response = self.client.post(
            signup_url,
            {
                "first_name": "Bobby",
                "last_name": "Burgers",
                "workspace": "Bobby's Burgers",
                "password1": "arstqwfp",
                "email": "bobbyburgers@burgers.com",
                "timezone": "America/New_York",
            },
        )

        self.assertRedirect(response, success_url)

    def test_change_password(self):

        # make sure we get the correct help text on change password page
        self.login(self.admin)

        change_password_url = reverse("account_change_password")
        response = self.client.get(change_password_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "At least 8 characters or more")
