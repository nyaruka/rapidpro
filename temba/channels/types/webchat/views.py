from smartmin.views import SmartFormView

from temba.channels.models import Channel
from temba.channels.views import ClaimViewMixin


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        pass

    form_class = Form
    readonly_servicing = False

    def form_valid(self, form):
        self.object = Channel.create(
            self.request.org, self.request.user, None, self.channel_type, name="WebChat", config={}
        )

        return super().form_valid(form)
