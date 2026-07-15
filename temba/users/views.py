import json

from allauth.account.views import LoginView, SignupView

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View

from temba.orgs.models import Invitation


class TembaInviteMixin:
    def get_form_kwargs(self):
        if self.request.method == "GET":
            # update our session invite on GET
            self.request.session["invite_secret"] = self.request.GET.get("invite", None)

        return {"secret": self.request.session.get("invite_secret", None), **super().get_form_kwargs()}

    @cached_property
    def invite(self):
        secret = self.request.session.get("invite_secret", None)
        if secret:
            return Invitation.objects.filter(secret=secret, is_active=True).first()
        return None

    def get_initial(self):
        initial = super().get_initial()
        if self.request.session.get("invite_secret", None) and not self.invite:
            messages.add_message(
                self.request,
                messages.WARNING,
                _("Sorry, your invitation is no longer valid. Please request a new invite."),
            )

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.invite:
            context["invite"] = self.invite
        return context


class UserSettingsView(LoginRequiredMixin, View):
    """
    Lets the current user update their own UI settings - posted top level keys are merged into the existing value.
    """

    # the settings keys the UI is allowed to write
    ALLOWED_KEYS = {"contact_cards"}

    def post(self, request, *args, **kwargs):
        if len(request.body) > 100_000:
            return JsonResponse({"error": "request body too large"}, status=400)

        try:
            posted = json.loads(request.body)
        except ValueError:
            posted = None

        if not isinstance(posted, dict):
            return JsonResponse({"error": "request body must be a JSON object"}, status=400)

        if not set(posted) <= self.ALLOWED_KEYS:
            return JsonResponse({"error": "unsupported settings keys"}, status=400)

        request.user.settings = {**request.user.settings, **posted}
        request.user.save(update_fields=("settings",))

        return JsonResponse({"settings": request.user.settings})


class TembaLoginView(TembaInviteMixin, LoginView):
    def get_initial(self):
        initial = super().get_initial()

        if self.invite:
            initial["login"] = self.invite.email
        return initial


class TembaSignupView(TembaInviteMixin, SignupView):
    def get_initial(self):
        initial = super().get_initial()

        if self.invite:
            initial["email"] = self.invite.email
        return initial
