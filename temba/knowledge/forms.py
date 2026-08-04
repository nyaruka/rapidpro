from django import forms
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.mixins import UniqueNameMixin
from temba.utils.fields import InputWidget, SelectWidget

from .models import Knowledge


class KnowledgeForm(UniqueNameMixin, forms.ModelForm):
    """
    Create form - the type picker plus the website-only settings.
    """

    knowledge_type = forms.ChoiceField(
        choices=(
            (Knowledge.TYPE_WEBSITE, _("Website")),
            (Knowledge.TYPE_DOCUMENTS, _("Documents")),
        ),
        label=_("Type"),
        widget=SelectWidget(attrs={"widget_only": False}),
    )
    url = forms.URLField(
        required=False,
        max_length=Knowledge.MAX_URL_LEN,
        label=_("URL"),
        widget=InputWidget(),
        help_text=_("The address to crawl, e.g. https://help.example.com"),
    )
    max_pages = forms.IntegerField(
        required=False, min_value=1, max_value=Knowledge.MAX_MAX_PAGES, label=_("Max Pages"), widget=InputWidget()
    )
    refresh = forms.ChoiceField(
        choices=Knowledge.REFRESH_CHOICES, required=False, label=_("Refresh"), widget=SelectWidget()
    )

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("knowledge_type") == Knowledge.TYPE_WEBSITE and not cleaned.get("url"):
            self.add_error("url", _("This field is required."))
        return cleaned

    class Meta:
        model = Knowledge
        fields = ("name", "knowledge_type", "url", "max_pages", "refresh")
        widgets = {"name": InputWidget()}


class KnowledgeUpdateForm(UniqueNameMixin, forms.ModelForm):
    """
    Update form - type is fixed; website sources also expose their crawl settings.
    """

    url = forms.URLField(required=True, max_length=Knowledge.MAX_URL_LEN, label=_("URL"), widget=InputWidget())
    max_pages = forms.IntegerField(
        required=False, min_value=1, max_value=Knowledge.MAX_MAX_PAGES, label=_("Max Pages"), widget=InputWidget()
    )
    refresh = forms.ChoiceField(
        choices=Knowledge.REFRESH_CHOICES, required=False, label=_("Refresh"), widget=SelectWidget()
    )

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org

        if self.instance.knowledge_type != Knowledge.TYPE_WEBSITE:
            for f in ("url", "max_pages", "refresh"):
                del self.fields[f]
        else:
            self.fields["url"].initial = self.instance.config.get(Knowledge.CONFIG_URL)
            self.fields["max_pages"].initial = self.instance.config.get(Knowledge.CONFIG_MAX_PAGES)
            self.fields["refresh"].initial = self.instance.config.get(Knowledge.CONFIG_REFRESH)

    class Meta:
        model = Knowledge
        fields = ("name",)
        widgets = {"name": InputWidget()}
