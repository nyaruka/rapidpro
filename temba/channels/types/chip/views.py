from smartmin.views import SmartFormView

from django.conf import settings

from temba.channels.models import Channel
from temba.channels.views import ClaimViewMixin
from temba.utils.text import generate_secret


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        pass

    form_class = Form
    readonly_servicing = False

    def form_valid(self, form):
        user = self.request.user
        org = self.request.org
        secret = generate_secret(40)

        self.object = Channel.create(
            org,
            user,
            None,
            self.channel_type,
            name="Web Chat",
            config={"secret": secret, "send_url": f"https://{settings.HOSTNAME}/wc/send"},
        )

        return super().form_valid(form)
