from allauth.account.adapter import DefaultAccountAdapter


class TembaAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form):
        """
        Save the user instance.
        """

        print("Saving user instance")

        # treat username as email for now, nothing stopping us from removing username though
        user.username = form.cleaned_data["email"]

        # Call the parent method to save the user instance
        super().save_user(request, user, form)
