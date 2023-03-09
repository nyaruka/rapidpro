from smartmin.views import SmartCRUDL, SmartUpdateView

from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.orgs.views import OrgObjPermsMixin
from temba.utils.fields import DateWidget, SelectMultipleWidget, SelectWidget, TembaDateTimeField
from temba.utils.views import ComponentFormMixin

from .models import Schedule


class ScheduleFormMixin(forms.Form):
    start_datetime = TembaDateTimeField(
        label=_("Start Time"),
    )
    repeat_period = forms.ChoiceField(choices=Schedule.REPEAT_CHOICES, label=_("Repeat"), widget=SelectWidget())
    repeat_days_of_week = forms.MultipleChoiceField(
        choices=Schedule.REPEAT_DAYS_CHOICES,
        label=_("Repeat On Days"),
        help_text=_("The days of the week to repeat on for weekly schedules"),
        required=False,
        widget=SelectMultipleWidget(attrs=({"placeholder": _("Select days")})),
    )

    def set_org(self, org):
        """
        Because this mixin is mixed with other forms it can't have a __init__ constructor that takes non standard Django
        forms args and kwargs, so we have to customize based on user after the form has been created.
        """

        tz = org.timezone
        start_datetime = self.fields["start_datetime"]
        start_datetime.help_text = _("First time this should happen in the %s timezone.") % tz

        # we want to edit schedules in the org's timezone
        start_datetime.widget = DateWidget(attrs={"timezone": tz, "time": True})

    def clean_repeat_days_of_week(self):
        value = self.cleaned_data["repeat_days_of_week"]

        # sort by Monday to Sunday
        value = sorted(value, key=lambda c: Schedule.DAYS_OF_WEEK_OFFSET.index(c))

        return "".join(value)

    def clean(self):
        cleaned_data = super().clean()

        if self.is_valid():
            repeat_period = cleaned_data["repeat_period"]
            repeat_days_of_week = cleaned_data.get("repeat_days_of_week")
            start_datetime = cleaned_data.get("start_datetime")

            if repeat_period == Schedule.REPEAT_WEEKLY and not repeat_days_of_week:
                self.add_error("repeat_days_of_week", _("Must specify at least one day of the week."))

            if repeat_period == Schedule.REPEAT_NEVER and start_datetime and start_datetime < timezone.now():
                self.add_error("start_datetime", _("Must specify a start time that is in the future."))

        return cleaned_data

    class Meta:
        fields = ("start_datetime", "repeat_period", "repeat_days_of_week")


class ScheduleCRUDL(SmartCRUDL):
    model = Schedule
    actions = ("update",)

    class Update(OrgObjPermsMixin, ComponentFormMixin, SmartUpdateView):
        class Form(forms.ModelForm, ScheduleFormMixin):
            def __init__(self, org, *args, **kwargs):
                super().__init__(*args, **kwargs)

                # we use a post with a blank date to mean unschedule
                self.fields["start_datetime"].required = False

                self.set_org(org)

            def clean(self):
                super().clean()

                ScheduleFormMixin.clean(self)

            class Meta:
                model = Schedule
                fields = ScheduleFormMixin.Meta.fields

        form_class = Form
        submit_button_name = "Start"
        success_message = ""

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["org"] = self.request.org
            return kwargs

        def derive_initial(self):
            schedule = self.get_object()

            initial = super().derive_initial()
            initial["start_datetime"] = schedule.next_fire
            initial["repeat_days_of_week"] = list(schedule.repeat_days_of_week) if schedule.repeat_days_of_week else []
            return initial

        def get_success_url(self):
            broadcast = self.get_object().get_broadcast()
            assert broadcast is not None
            return reverse("msgs.broadcast_scheduled_read", args=[broadcast.id])

        def save(self, *args, **kwargs):
            self.object.update_schedule(
                self.request.user,
                self.form.cleaned_data["start_datetime"],
                self.form.cleaned_data["repeat_period"],
                self.form.cleaned_data.get("repeat_days_of_week"),
            )
