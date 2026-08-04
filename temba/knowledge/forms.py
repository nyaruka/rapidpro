from django import forms
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.mixins import UniqueNameMixin
from temba.utils import languages
from temba.utils.fields import InputWidget, SelectWidget

from .models import Article, Knowledge


class MarkdownEditorWidget(forms.Widget):
    """
    The article body editor - a rich editor over the article's markdown, with a formatting toolbar and screenshot
    uploads. It renders client side, escaping raw HTML the same way the read page does.
    """

    template_name = "knowledge/forms/markdown_editor.html"
    is_annotated = True


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


class ArticleForm(forms.ModelForm):
    """
    Create and update form for a helpdesk article. Publishing isn't here - it's an explicit action of its own, so that
    saving an edit can never silently make a draft public.
    """

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "body" in self.fields:  # the create form asks only for a title
            self.fields["body"].max_length = Article.MAX_BODY_LEN

        # an article keeps the language it was written in even if the workspace later drops it, so that language stays
        # a choice here - otherwise the article could never be saved again
        codes = list(org.flow_languages)
        if self.instance.language and self.instance.language not in codes:
            codes.append(self.instance.language)

        # only worth asking which language an article is in when there's actually more than one to choose from
        if len(codes) > 1:
            self.fields["language"].choices = [(c, languages.get_name(c)) for c in codes]
        else:
            del self.fields["language"]

    class Meta:
        model = Article
        fields = ("title", "language", "body")
        widgets = {
            "title": InputWidget(attrs={"widget_only": False}),
            "language": SelectWidget(attrs={"widget_only": False}),
            "body": MarkdownEditorWidget(),
        }
        labels = {"title": _("Title"), "language": _("Language"), "body": _("Body")}


class ArticleCreateForm(ArticleForm):
    """
    New articles are created with just a title - the body is written on the editor page they land on.
    """

    class Meta(ArticleForm.Meta):
        fields = ("title", "language")
