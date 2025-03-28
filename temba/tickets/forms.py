from django import forms
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.mixins import UniqueNameMixin

from .models import Shortcut, Team, Topic


class ShortcutForm(UniqueNameMixin, forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org

    class Meta:
        model = Shortcut
        fields = ("name", "text")


class TeamForm(UniqueNameMixin, forms.ModelForm):
    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.none(), required=False)

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org
        self.fields["topics"].queryset = org.topics.filter(is_active=True)

    def clean_topics(self):
        topics = self.cleaned_data["topics"]
        if len(topics) > Team.max_topics:
            raise forms.ValidationError(
                _("Teams can have at most %(limit)d topics."), params={"limit": Team.max_topics}
            )
        return topics

    class Meta:
        model = Team
        fields = ("name", "topics")


class TopicForm(UniqueNameMixin, forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org

    class Meta:
        model = Topic
        fields = ("name",)
