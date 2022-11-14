"""
Written by Keeya Emmanuel Lubowa
On 27th Aug, 2022
Email ekeeya@oddjobs.tech
"""

from ast import literal_eval

import redis
import requests
from django.conf import settings
from django.http import QueryDict
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, BasicAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework import status

from temba.ussd.models import NONE, TOKEN, JWT, COMPLETED, TIMED_OUT, USSDContact
from temba.ussd.renderers import PlainTextRenderer, CustomXMLRenderer
from rest_framework_xml.renderers import XMLRenderer

from temba.ussd.utils import ussd_logger, ProcessAggregatorRequest, standard_urn, FLOW_WAITING_FLAG, \
    changeSessionStatus, STANDARD_TEXT, STANDARD_FROM, get_receive_url

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded'  # for now this is what works with flow-executor last I checked
}


class SendURL(APIView):
    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]

    def post(self, request):
        try:
            content = request.data.dict()
            ussd_logger.info(f"From Flow-executor: {content}")
            # decrement key1
            to = content['to_no_plus']
            key2 = f"USSD_MSG_KEY_{to}"
            r.lpush(key2, str(content))
            return Response({"message": "success"}, status=200)
        except Exception as err:
            ussd_logger.exception(err)


class USSDCallBack(APIView):
    authentication_classes = []
    permission_classes = []
    request = None
    request_factory = None
    standard_request_string = None
    renderer_classes = (JSONRenderer, PlainTextRenderer, XMLRenderer, CustomXMLRenderer)

    def perform_authentication(self, request):
        # overriding perform_authentication method from APIView
        # to examine the request and decide whether we apply authentication, which scheme or not
        # Some legacy USSD gateways do not support authentication (Can you imagine?)
        self.request = request
        if request.method == "GET":
            request_data = request.query_params.dict()
        else:
            if isinstance(request.data, QueryDict):
                request_data = request.data.dict()
            else:
                request_data = request.data
        ussd_logger.info(request_data)
        self.request_factory = ProcessAggregatorRequest(request_data)
        self.standard_request_string = self.request_factory.process_handler()
        auth_scheme = self.request_factory.get_auth_scheme

        # we shall support NONE, TOKEN and BASIC
        if auth_scheme == NONE:
            self.authentication_classes = []
            self.permission_classes = []
        elif auth_scheme == TOKEN:
            # add token authentication class
            self.authentication_classes.append(TokenAuthentication)
            self.permission_classes.append(IsAuthenticated)
        else:
            # This is basic Authentication
            self.authentication_classes.append(BasicAuthentication)

    def process_request(self):
        ussd_session = self.request_factory.save_ussd_session()
        is_new_session = self.request_factory.is_new_session
        still_in_flow = self.request_factory.is_in_flow
        handler = self.request_factory.get_handler
        end_action, reply_action = self.request_factory.flow_exit_or_continue_signal
        urn = self.standard_request_string[STANDARD_FROM]

        channel = handler.channel

        if is_new_session:
            # send the flow executor and empty string if enable_repeat_current_step is enabled to ensure they start
            # from their current step in the flow else send them a flow start trigger
            if handler.enable_repeat_current_step:
                text = " " if still_in_flow else handler.trigger_word
            else:
                text = handler.trigger_word
        else:
            text = self.standard_request_string[STANDARD_TEXT].strip()
        standard_contact = standard_urn(urn)
        flow_request_body = {
            "from": standard_contact,
            "text": text
        }
        ussd_logger.info(flow_request_body)

        # create redis keys
        key1 = f"USSD_MO_MT_KEY_{standard_contact}"
        r.set(key1, 1)
        key2 = f"USSD_MSG_KEY_{standard_contact}"

        # get the shortcode receive channel to send msgs to the flow executor

        try:
            receive_url = get_receive_url(channel)
            req = requests.post(receive_url, flow_request_body, headers=HEADERS, timeout=10)
            if req.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
                # increment key1
                r.incr(key1)
                r.expire(key1, 30)  # expire key1 after 30 s
                data = r.blpop(key2, 15)# wait for configured time out for flow executor  #TODO this should be configurable
                if data:
                    feedback = literal_eval(data[1].decode("utf-8"))
                    if 'session_status' not in feedback:
                        raise Exception("session_status was not returned in flow executor response")
                    text = feedback['text']
                    flow_session_status = feedback['session_status']
                    ussd_logger.info(f"From redis key: {data}")

                    if flow_session_status == FLOW_WAITING_FLAG:
                        action = reply_action
                    else:
                        # mark session complete and give it a green badge
                        changeSessionStatus(ussd_session, COMPLETED, 'success')
                        action = end_action
                    flow_executor_response = dict(text=text, action=action)
                else:
                    # mark session timed out and give it a red badge
                    changeSessionStatus(ussd_session, TIMED_OUT, 'danger')
                    ussd_logger.error(f"Response timed out for redis key {key2}")
                    flow_executor_response = dict(text="Response timed out", action=end_action)
                    # let's just delete this contact
                    USSDContact.contacts.delete_contact_by_urn(standard_contact)
                r.delete(key2)  # let's delete the key after use
            else:
                changeSessionStatus(ussd_session, TIMED_OUT, 'danger')
                flow_executor_response = dict(text="Oops,An Error Occurred", action=end_action)
                USSDContact.contacts.delete_contact_by_urn(standard_contact)
                ussd_logger.error(req.content)

        except Exception as error:
            ussd_logger.exception(error)
            flow_executor_response = dict(text="External application error", action=end_action)

        aggregator_response = self.request_factory.construct_expected_response(flow_executor_response)

        return aggregator_response

    def construct_response(self):
        response_data = self.process_request()

        if isinstance(response_data, dict):
            if response_data.pop("is_header", None):
                header_key = response_data.pop("header_key", None)
                header_value = response_data.pop("header_value", None)
                if not response_data.pop("is_plain", None):
                    response = Response(response_data, status=status.HTTP_200_OK)
                    response[header_key] = header_value
                else:
                    # plain text
                    response = Response(response_data[STANDARD_TEXT], status=status.HTTP_200_OK)
                    response[header_key] = header_value
                return response
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request):
        return self.construct_response()

    def get(self, request):
        return self.construct_response()


class WebHookTester(APIView):
    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]

    def post(self, request):
        data = request.data
        response = dict(
            name="Shipping Eggs",
            age=28,
            status="Shipped",
            ship_date=timezone.now(),
            delivery_date=timezone.now(),
            description="This is a simple description",
            cancel_date=timezone.now()
        )
        return Response(response, status.HTTP_200_OK)


