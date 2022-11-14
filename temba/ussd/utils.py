"""
Written by Keeya Emmanuel Lubowa
On 27th Aug, 2022
Email ekeeya@oddjobs.tech

"""

import logging
import re

from django.conf import settings
from django.utils import timezone

from temba.channels.models import Channel
from temba.ussd.models import STARTS_WITH, ENDS_WITH, IS_IN_RESPONSE_BODY, IS_IN_HEADER_XML_JSON, Handler, USSDContact, \
    Session, IN_PROGRESS, TIMED_OUT, TERMINATED
from temba.utils.ussd import standard_urn

ussd_logger = logging.getLogger('ussd')
STANDARD_FROM = "from"
STANDARD_TEXT = "text"
STANDARD_SHORT_CODE = "short_code"
STANDARD_SESSION_ID = "session_id"
STANDARD_ACTION = "action"

MANDATORY_STANDARD_MAP_REQUEST_FIELDS = [STANDARD_FROM, STANDARD_TEXT, STANDARD_SHORT_CODE, STANDARD_SESSION_ID]

MANDATORY_STANDARD_MAP_RESPONSE_FIELDS = [STANDARD_TEXT, STANDARD_ACTION]

FLOW_WAITING_FLAG = "W"


def changeSessionStatus(session, status, badge):
    session.status = status
    session.badge = badge
    session.save()


def get_receive_url(channel: Channel) -> str:
    channel_uuid = channel.uuid
    protocol = "http"
    host = '127.0.0.1'
    port = "8080"
    return f"{protocol}://{host}:{port}/c/ex/{channel_uuid}/receive"


def separate_keys(string):
    """'
    @string => a string in the format of "{{short_code=ussdServiceCode}},  {{session_id=transactionId}}"
    will generate [short_code, session_id] and [ussdServiceCode, transactionId]
    """
    system_keys = []
    aggregator_keys = []
    matches = re.compile('{{(.*?)}}', re.DOTALL).findall(string)
    if not isinstance(matches, list) or len(matches) < 1:
        raise Exception(f"Wrong string format for parsed string: {string}")
    for match in matches:
        split_list = match.split("=")
        system_keys.append(split_list[0].strip())
        aggregator_keys.append(split_list[1].strip())

    return [system_keys, aggregator_keys]


def sanitize_shortcode(code: str) -> str:
    """
     Remove leading * and trialing # if it exists on a shortcode
    """
    code = code.strip()
    if len(code) > 1:
        if code[0] == "*":
            code = code[1:]
        if code[-1:] == "#":
            code = code[:-1]
    return code


class ProcessAggregatorRequest:
    system_request_fields = MANDATORY_STANDARD_MAP_REQUEST_FIELDS
    aggregator_expected_fields = []
    standard_request = ''
    service_code = ''
    contact = None
    still_in_flow = False
    is_session_start = None
    handler = None

    # constructor takes in a dict of aggregator request params and sets them
    def __init__(self, aggregator_request: dict):
        self.request_data = aggregator_request

    def check_mandatory_keys(self, key: str) -> bool:
        """
            check if a mandatory key exists in the request_format mapping
            mandatory keys are [from, text, session_id, short_code]
        """
        if key in self.request_data:
            return True
        else:
            error = f"Make sure your {{{key}=someThing}} is defined in aggregator  {self.handler.aggregator}'s " \
                    f"handler Request Format field"
            ussd_logger.error(error)
            raise Exception(error)

    def construct_standard_request(self):
        """
            Different aggregators send request with varying parameter names.
            What we ar sure of is they all send parameters with similar meaning
            e.g., one might send ussdServiceCode and another can name it ussdCode

            We need a way to translate and map these to our standard representation.
            In the aggregator handler, you configure the request_structure field where you map these to system standard
            names.
            for example, {{from=msisdn, ussdServiceCode=short_code}} means the aggregator will send msisdn but we
            interpret it as from and ussdServiceCode is interpreted as short_code.
            another aggregator handle can map them as {{from=telNumber, serviceCode=short_code}}

            The purpose of this function is to map these to the standard nomenclature.
            The standard system nomenclature is [from, short_code, timestamp, session_id, text]
        """
        not_in_template = []  # all keys not mapped in the request_format but exist in the request
        map_list = [
            (self.system_request_fields[self.aggregator_expected_fields.index(key)],
             key) if key in self.aggregator_expected_fields else (
                not_in_template.append(key)) for
            key in self.request_data.keys()]

        # drop all we never mapped in the request_format
        [self.request_data.pop(v, None) for v in not_in_template if len(not_in_template) > 0]

        for item in map_list:
            if item is not None:
                # update request_data with new standard key names
                self.request_data[item[0]] = self.request_data.pop(item[1])
        # ensure we have all mandatory map fields set in the constructed request data from the handler's request format
        for mandatory_key in MANDATORY_STANDARD_MAP_REQUEST_FIELDS:
            self.check_mandatory_keys(mandatory_key)

        # set standard_request
        self.standard_request = self.request_data
        ussd_logger.info(self.standard_request)

    def construct_expected_response(self, response_data):
        """
          Different aggregators expect different response structures and formats. They clearly discuss this in their
          documentations.
          In here, we try to cater for a few that we know of.
          Now, DRF will automatically determine the response format content/type when sending the response back to
          the aggregator if they specify the "Accept" header in the request. Our hands are tied if this header is not
          fixed, so by default we shall return json. the rest of the formats can be plain text, XML or JSON

          Besides the format above, just like request_structure, the handler specifies a response_structure for
          aggregators who expect NONE Plain text response. For example, for JSON and XML, we must define keys and these
          are mapped from standard system keys to what the aggregator understands.
          Let's look at this, if aggregator A expects a json response below in order to render the right menu to the
          end user device
          {
            "responseString":"Hello how are you",
            "menuType" :"C/E" // to indicate which menu to render (response or exit)
          }
          the system standard response values are [text, action] so we must configure the handler's
          response_structure to map the standards above to what the aggregator understands, basically we are
          reversing what we did for requests. so the response_structure configuration to acquire this will be {{
          text=responseString}} {{action=menuType}}.
          This is similar for XML.

          Since some aggregators expect flag that specifies which kind of menu to render at the user's device as one
          of the response header, we shall also cater for this.

          Many aggregators have different expectations, you can always modify this function to carter for any
          special cases.

          With that lets proceed
          @param response_data consists of the response text and a flag showing if user is expected to respond or at
          the flow exit.
        """
        if all(key in response_data for key in MANDATORY_STANDARD_MAP_RESPONSE_FIELDS):
            text = response_data['text']
            action = response_data["action"]
            if self.handler:
                response_structure = self.handler.response_structure
                # extract our response mapped fields
                standard_keys, aggregator_expected_keys = separate_keys(response_structure)
                text_index = standard_keys.index("text")
                action_index = standard_keys.index("action")

                # let's examine handler settings to determine how to send our request
                # start with how to expect response or exit flag mode is
                flag_mode = self.handler.signal_exit_or_reply_mode
                if flag_mode in [STARTS_WITH, ENDS_WITH]:
                    # handle starts with (these most probably expect plain text, so they want the menu type
                    # indicator flag to be at the beginning or end of the response string.
                    if flag_mode == 1:
                        # start with
                        response = f"{action.upper()} {text}"
                    else:
                        # ends with
                        response = f"{text} {action.upper()}"
                elif flag_mode == IS_IN_RESPONSE_BODY:
                    # flag is part of the response body in this case we shall need to know how its called
                    response = {
                        aggregator_expected_keys[text_index]: text,
                        aggregator_expected_keys[action_index]: action
                    }
                elif flag_mode == IS_IN_HEADER_XML_JSON:
                    # flag is in the response headers but response is not plain text
                    response = {
                        "is_header": True,
                        "is_plain": False,
                        "header_key": self.handler.signal_header_key,
                        "header_value": action,
                        aggregator_expected_keys[text_index]: text
                    }
                else:
                    # flag is in response headers but response format is plain text
                    response = {
                        "is_header": True,
                        "is_plain": True,
                        "header_key": self.handler.signal_header_key,
                        "header_value": action,
                        "text": text
                    }
                return response
        else:
            raise Exception(
                f"Bad response data {response_data}. missing one or both required fields [text, action]. Ensure "
                f"format conforms to [{{text=..}},{{action=..}}]'"
            )

    @property
    def is_new_session(self) -> bool:
        """
         returns boolean indicating whether it's a new session
        """
        return self.is_session_start

    @property
    def is_in_flow(self) -> bool:
        """
         return boolean depending on whether user is still in the flow or not
        """
        return self.still_in_flow

    def set_handler(self):
        """
            This method looks at the aggregator request and determines the shortcode and sets the handler
            If it is not set, we default to the default short code.
            Most aggregators return this field. It might be named differently but its just the shortcode the user
            dials which it also known to you since you paid for it e.g. *255#. Note that the function will omit the *#
            Since we do not know how the aggregator calls a shortcode, yet we need it to set the handler,
            This presents us some kind of chicken-egg problem lets work around it
        """
        # let's get all the short codes we have (assuming they are not in thousands)
        short_codes = Handler.objects.values_list('short_code', flat=True)
        standard_short_codes = []
        for code in short_codes:
            standard_short_codes.append(sanitize_shortcode(code))

        set_codes = set(standard_short_codes)
        # We assume the code is there in our request values so lets get the request_data values
        request_values = []
        for value in self.request_data.values():
            # just in case input is nothing
            if len(str(value).strip()):
                request_values.append(sanitize_shortcode(value))
        intersection = set_codes.intersection(set(request_values))
        if len(intersection) == 1:
            # we have a ussd dial code in request_data
            self.service_code = list(intersection)[0]
        else:
            # the aggregator probably does not return the code use the default one from settings or you did not
            # configure a handler for this short code
            if Handler.objects.filter(short_code=settings.DEFAULT_SHORT_CODE).exists():
                self.service_code = sanitize_shortcode(str(settings.DEFAULT_SHORT_CODE))
            else:
                raise Exception(
                    "This aggregator most likely has no handler or a wrong shortcode was registered when creating a "
                    "handler check spelling of the code in the subsequent handler record and try again")

        # set the handler and all is well
        self.handler = Handler.objects.get(short_code=self.service_code)

    def is_in_flow_session(self):
        """
            To find out if a contact hasn't completed a flow, we check the status of their last session entry.
            if it's In Progress or Timed Out, then we are safe to say they are still in a flow
        """
        query_params = dict(contact=self.contact, handler=self.handler)
        last_session = Session.sessions.session_by_fields(query_params)
        if last_session:
            if last_session.status in [IN_PROGRESS, TIMED_OUT]:
                self.still_in_flow = True
            else:
                self.still_in_flow = False
        else:
            self.still_in_flow = False

    def save_ussd_session(self):
        """
         this function basically manages ussd sessions
        """
        session_id = self.standard_request['session_id']
        query_params = dict(session_id=session_id)
        session = Session.sessions.session_by_fields(query_params)
        if session:
            session.modified_on = timezone.now()
            session.save()
            self.is_session_start = False
        else:
            # First End all in progress and timed out sessions attached to this contact if any
            query_params = dict(contact=self.contact, handler=self.handler, status=IN_PROGRESS)
            query_params2 = dict(contact=self.contact, handler=self.handler, status=TIMED_OUT)
            in_progress_sessions = Session.sessions.sessions_by_fields(query_params)
            timed_out_sessions = Session.sessions.sessions_by_fields(query_params2)
            in_progress_sessions.update(status=TERMINATED, badge='dark')
            timed_out_sessions.update(status=TERMINATED, badge='dark')

            kwargs = dict(session_id=session_id, contact=self.contact, handler=self.handler)
            session = Session.objects.create(**kwargs)
            self.is_session_start = True
        return session

    def save_ussd_contact(self):
        """
        Saves a ussd contact to for tracking the ussd session
        """
        urn = standard_urn(self.standard_request['from'])
        contact_of_interest, _ = USSDContact.objects.get_or_create(urn=urn)
        self.contact = contact_of_interest
        self.is_in_flow_session()

    @property
    def get_auth_scheme(self):
        """
            return handler auth_scheme as param
        """
        return self.handler.auth_scheme if self.handler else None

    @property
    def get_handler(self):
        """
        update last accessed value and return handler object
        """
        #
        self.handler.last_accessed_at = timezone.now()
        self.handler.save()
        return self.handler

    @property
    def flow_exit_or_continue_signal(self):
        return self.handler.signal_menu_type_strings.split(",")

    def process_handler(self):
        """
            We shall call this from outside to put everything together
        """
        # determine service_code
        self.set_handler()
        self.system_request_fields, self.aggregator_expected_fields = separate_keys(self.handler.request_structure)

        # generate standard request_String to send to the flows
        self.construct_standard_request()
        # Save contact to ussd_contact if it's new
        self.save_ussd_contact()
        return self.standard_request
