import abc
import logging

from django.template import Context, Engine
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


class AnalyticsBackend(metaclass=abc.ABCMeta):
    slug: str = None
    hook_templates = {}

    def identify(self, user, brand: dict, org):
        """
        Creates and identifies a new user
        """

    def get_hook_template(self, name: str) -> str:
        """
        Gets template name for named hook
        """
        return self.hook_templates.get(name)

    def get_hook_context(self, request) -> dict:
        """
        Gets context to be included in hook templates
        """
        return {}


class ConsoleBackend(AnalyticsBackend):
    """
    An example analytics backend which just prints to the console
    """

    slug = "console"


def get_backends() -> list:
    from . import backends

    return list(backends.values())


def identify(user, brand, org):
    """
    Creates and identifies a new user to our analytics backends
    """
    for backend in get_backends():
        try:
            backend.identify(user, brand, org)
        except Exception:
            logger.exception(f"error identifying user on {backend.slug}")


def get_hook_html(name: str, context) -> str:
    """
    Gets HTML to be inserted at the named template hook
    """
    engine = Engine.get_default()
    html = ""
    for backend in get_backends():
        template_name = backend.get_hook_template(name)
        if template_name:
            with context.update(backend.get_hook_context(context.request)):
                html += f"<!-- begin hook for {backend.slug} -->\n"
                html += engine.get_template(template_name).render(Context(context))
                html += f"<!-- end hook for {backend.slug} -->\n"

    return mark_safe(html)
