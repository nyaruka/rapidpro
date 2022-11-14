"""
Written by Keeya Emmanuel Lubowa
On 24th Aug, 2022
Email ekeeya@oddjobs.tech
"""

from django import forms
from .models import Handler
import socket

from ..utils.fields import InputWidget, SelectWidget, CompletionTextarea, CheckboxWidget

hostname = f"https://{socket.gethostname()}"

CONFIG_DEFAULT_REQUEST_STRUCTURE = (
    "{{short_code=serviceCode}},  {{session_id=sessionId}}, {{from= msisdn}}, {{text=input}}"
)
CONFIG_DEFAULT_RESPONSE_STRUCTURE = (
    "{{text=responseString}},  {{action=continueSession}}"
)


class HandlerForm(forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        self.fields['response_structure'].required = False
        self.fields['request_structure'].initial = CONFIG_DEFAULT_REQUEST_STRUCTURE
        self.fields['response_structure'].initial = CONFIG_DEFAULT_RESPONSE_STRUCTURE

    class Meta:
        model = Handler
        exclude = ["is_active", "uuid"]
        widgets = {"short_code": InputWidget(),
                   "aggregator": InputWidget(),
                   "channel": SelectWidget(),
                   "request_structure": CompletionTextarea(),
                   "response_structure": CompletionTextarea(),
                   "signal_exit_or_reply_mode": SelectWidget(),
                   "signal_menu_type_strings": InputWidget(),
                   "signal_header_key": InputWidget(),
                   "trigger_word": InputWidget(),
                   "enable_repeat_current_step": CheckboxWidget(),
                   "auth_scheme": SelectWidget(),
                   }
