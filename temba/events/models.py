import hashlib
import json
import requests
import time

from django.conf import settings
from django.db import models
from django.utils import timezone

from smartmin.models import SmartModel
from temba.api.models import get_api_user

from temba.channels.models import Channel
from temba.contacts.models import TEL_SCHEME
from temba.orgs.models import Org, TRANSFERTO_ACCOUNT_LOGIN, TRANSFERTO_AIRTIME_API_TOKEN
from temba.utils import datetime_to_str, get_country_code_by_name


class AirtimeEvent(SmartModel):
    TRANSFERTO_AIRTIME_API_URL = 'https://fm.transfer-to.com/cgi-bin/shop/topup'
    LOG_DIVIDER = "%s\n\n\n" % ('=' * 20)

    PENDING = 'P'
    COMPLETE = 'C'
    FAILED = 'F'

    STATUS_CHOICES = ((PENDING, "Pending"),
                      (COMPLETE, "Complete"),
                      (FAILED, "Failed"))

    org = models.ForeignKey(Org,
                            help_text="The organization that this event was triggered for")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P',
                              help_text="The state this event is currently in")
    channel = models.ForeignKey(Channel, null=True, blank=True,
                                help_text="The channel that this event is relating to")
    recipient = models.CharField(max_length=64)
    amount = models.FloatField()
    denomination = models.CharField(max_length=32, null=True, blank=True)
    transaction_id = models.CharField(max_length=256, null=True, blank=True)
    reference_operator = models.CharField(max_length=64, null=True, blank=True)
    airtime_amount = models.CharField(max_length=32, null=True, blank=True)
    last_message = models.CharField(max_length=256, null=True, blank=True)
    data = models.TextField(null=True, blank=True)
    event_log = models.TextField(null=True, blank=True)

    @classmethod
    def post_transferto_api_response(cls, login, token, **kwargs):
        key = str(int(time.time()))
        md5 = hashlib.md5()
        md5.update(login + token + key)
        md5 = md5.hexdigest()

        data = kwargs
        data.update(dict(login=login, key=key, md5=md5))

        if not settings.SEND_WEBHOOKS:
            raise Exception("!! Skipping WebHook send, SEND_WEBHOOKS set to False")

        response = requests.post(cls.TRANSFERTO_AIRTIME_API_URL, data)

        return response

    @classmethod
    def translate_transferto_response_content_as_json(cls, content):
        splitted_content = content.split('\r\n')
        output = dict()

        for elt in splitted_content:
            if elt and elt.find('=') > 0:
                key, val = tuple(elt.split('='))
                if val.find(',') > 0:
                    val = val.split(',')

                output[key] = val

        return output

    def get_transferto_response_json(self, **kwargs):
        config = self.org.config_json()
        login = config.get(TRANSFERTO_ACCOUNT_LOGIN, '')
        token = config.get(TRANSFERTO_AIRTIME_API_TOKEN, '')

        response = AirtimeEvent.post_transferto_api_response(login, token, **kwargs)
        content_json = AirtimeEvent.translate_transferto_response_content_as_json(response.content)

        return response.status_code, content_json, response.content

    @classmethod
    def trigger_flow_event(cls, flow, run, ruleset, contact, event):
        org = flow.org
        api_user = get_api_user()

        json_time = datetime_to_str(timezone.now())

        # get the results for this contact
        results = flow.get_results(contact)
        values = []

        if results and results[0]:
            values = results[0]['values']
            for value in values:
                value['time'] = datetime_to_str(value['time'])
                value['value'] = unicode(value['value'])

        # if the action is on the first node
        # we might not have an sms (or channel) yet
        channel = None
        text = None
        contact_urn = contact.get_urn()

        if event and not contact.is_test:
            text = event.text
            channel = event.channel
            contact_urn = event.contact_urn

        if not contact_urn:
            contact_urn = contact.get_urn()

        if channel:
            channel_id = channel.pk
        else:
            channel_id = -1

        steps = []
        for step in run.steps.all().order_by('arrived_on'):
            steps.append(dict(type=step.step_type,
                              node=step.step_uuid,
                              arrived_on=datetime_to_str(step.arrived_on),
                              left_on=datetime_to_str(step.left_on),
                              text=step.get_text(),
                              value=step.rule_value))

        data = dict(channel=channel_id,
                    flow=flow.id,
                    run=run.id,
                    text=text,
                    step=unicode(ruleset),
                    phone=contact.get_urn_display(org=org, scheme=TEL_SCHEME, full=True),
                    contact=contact.uuid,
                    urn=unicode(contact_urn),
                    values=json.dumps(values),
                    steps=json.dumps(steps),
                    time=json_time,
                    transferto_dumps=dict())

        airtime_event = AirtimeEvent.objects.create(org=org, channel=channel, recipient=contact_urn.path,
                                                    amount=0, data=json.dumps(data), event_log='',
                                                    created_by=api_user,
                                                    modified_by=api_user)

        message = "None"
        try:
            action = 'msisdn_info'
            request_kwargs = dict(action=action, destination_msisdn=airtime_event.recipient)
            status_code, content_json, content = airtime_event.get_transferto_response_json(**request_kwargs)

            error_code = int(content_json.get('error_code', None))
            error_txt = content_json.get('error_txt', None)

            if error_code != 0:
                message = "Got non-zero error code (%d) from TransferTo with message (%s)" % (error_code, error_txt)
                airtime_event.status = AirtimeEvent.FAILED
                raise Exception(message)

            country_name = content_json.get('country', '')
            country_code = get_country_code_by_name(country_name)
            amount_config = ruleset.config_json()
            country_config = amount_config.get(country_code, dict())
            amount = country_config.get('amount', 0)

            data['transferto_dumps'][action] = dict(status_code=status_code, data=content_json)
            airtime_event.amount = amount
            airtime_event.data = json.dumps(data)
            airtime_event.event_log += content + AirtimeEvent.LOG_DIVIDER

            product_list = content_json.get('product_list', [])

            if not isinstance(product_list, list):
                product_list = [product_list]

            targeted_prices = [float(i) for i in product_list if float(i) <= float(amount)]

            denomination = None
            if targeted_prices:
                denomination = max(targeted_prices)
                airtime_event.denomination = denomination

            if float(amount) <= 0:
                message = "Failed by invalid amount configuration or missing amount configuration for %s" % country_name
                airtime_event.status = AirtimeEvent.FAILED
                raise Exception(message)

            if denomination is None:
                message = "No TransferTo denomination matched"
                airtime_event.status = AirtimeEvent.FAILED
                raise Exception(message)

            action = 'reserve_id'
            request_kwargs = dict(action=action)
            status_code, content_json, content = airtime_event.get_transferto_response_json(**request_kwargs)

            error_code = int(content_json.get('error_code', None))
            error_txt = content_json.get('error_txt', None)

            if error_code != 0:
                message = "Got non-zero error code (%d) from TransferTo with message (%s)" % (error_code, error_txt)
                airtime_event.status = AirtimeEvent.FAILED
                raise Exception(message)

            transaction_id = content_json.get('reserve_id')

            data['transferto_dumps'][action] = dict(status_code=status_code, data=content_json)
            airtime_event.data = json.dumps(data)
            airtime_event.event_log += content + AirtimeEvent.LOG_DIVIDER
            airtime_event.transaction_id = transaction_id

            action = 'topup'
            request_kwargs = dict(action=action,
                                  reserve_id=transaction_id,
                                  msisdn=channel.address if channel else '',
                                  destination_msisdn=airtime_event.recipient,
                                  product=airtime_event.denomination)
            status_code, content_json, content = airtime_event.get_transferto_response_json(**request_kwargs)

            data['transferto_dumps'][action] = dict(status_code=status_code, data=content_json)
            airtime_event.data = json.dumps(data)
            airtime_event.event_log += content + AirtimeEvent.LOG_DIVIDER

            error_code = int(content_json.get('error_code', None))
            error_txt = content_json.get('error_txt', None)

            if error_code != 0:
                message = "Got non-zero error code (%d) from TransferTo with message (%s)" % (error_code, error_txt)
                airtime_event.status = AirtimeEvent.FAILED
                raise Exception(message)

            message = "Airtime Transferred Successfully"
            airtime_event.status = AirtimeEvent.COMPLETE

        except Exception as e:
            import traceback
            traceback.print_exc()

            airtime_event.status = AirtimeEvent.FAILED
            message = "Error transferring airtime: %s" % unicode(e)

        finally:
            airtime_event.last_message = message
            airtime_event.save()

        return airtime_event
