import logging
from dataclasses import asdict, dataclass, field

import requests

from django.conf import settings

from temba.utils import json

from .exceptions import (
    FlowValidationException,
    QueryValidationException,
    RequestException,
    URNValidationException,
    EmptyBroadcastException,
)
from ..modifiers import Modifier

logger = logging.getLogger(__name__)


@dataclass
class ContactSpec:
    """
    Describes a contact to be created
    """

    name: str
    language: str
    urns: list[str]
    fields: dict[str, str]
    groups: list[str]


@dataclass
class Inclusions:
    group_uuids: list = field(default_factory=list)
    contact_uuids: list = field(default_factory=list)
    query: str = ""


@dataclass
class Exclusions:
    non_active: bool = False  # contacts who are blocked, stopped or archived
    in_a_flow: bool = False  # contacts who are currently in a flow (including this one)
    started_previously: bool = False  # contacts who have been in this flow in the last 90 days
    not_seen_since_days: int = 0  # contacts who have not been seen for more than this number of days


@dataclass(frozen=True)
class QueryMetadata:
    """
    Contact query metadata
    """

    attributes: list = field(default_factory=list)
    schemes: list = field(default_factory=list)
    fields: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    allow_as_group: bool = False


@dataclass(frozen=True)
class ParsedQuery:
    query: str
    metadata: QueryMetadata


@dataclass(frozen=True)
class SearchResults:
    query: str
    total: int
    contact_ids: list
    metadata: QueryMetadata


@dataclass(frozen=True)
class BroadcastPreview:
    query: str
    total: int


@dataclass(frozen=True)
class StartPreview:
    query: str
    total: int


@dataclass
class URNResult:
    normalized: str
    contact_id: int = None
    error: str = None
    e164: bool = False


@dataclass
class ScheduleSpec:
    """
    Describes a schedule to be created
    """

    start: str
    repeat_period: str
    repeat_days_of_week: str = None


class MailroomClient:
    """
    Basic web client for mailroom
    """

    default_headers = {"User-Agent": "Temba"}

    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = self.default_headers.copy()
        if auth_token:
            self.headers["Authorization"] = "Token " + auth_token

    def version(self):
        return self._request("", post=False).get("version")

    def android_event(self, org_id: int, channel_id: int, phone: str, event_type: str, extra: dict, occurred_on):
        payload = {
            "org_id": org_id,
            "channel_id": channel_id,
            "phone": phone,
            "event_type": event_type,
            "extra": extra,
            "occurred_on": occurred_on.isoformat(),
        }

        return self._request("android/event", payload)

    def android_message(self, org_id: int, channel_id: int, phone: str, text: str, received_on):
        payload = {
            "org_id": org_id,
            "channel_id": channel_id,
            "phone": phone,
            "text": text,
            "received_on": received_on.isoformat(),
        }

        return self._request("android/message", payload)

    def contact_create(self, org_id: int, user_id: int, contact: ContactSpec):
        payload = {"org_id": org_id, "user_id": user_id, "contact": asdict(contact)}

        return self._request("contact/create", payload)

    def contact_export(self, org_id: int, group_id: int, query: str):
        payload = {"org_id": org_id, "group_id": group_id, "query": query}

        return self._request("contact/export", payload)

    def contact_export_preview(self, org_id: int, group_id: int, query: str):
        payload = {"org_id": org_id, "group_id": group_id, "query": query}

        return self._request("contact/export_preview", payload)

    def contact_inspect(self, org_id: int, contact_ids: list[int]):
        payload = {"org_id": org_id, "contact_ids": contact_ids}

        return self._request("contact/inspect", payload)

    def contact_interrupt(self, org_id: int, user_id: int, contact_id: int):
        payload = {"org_id": org_id, "user_id": user_id, "contact_id": contact_id}

        return self._request("contact/interrupt", payload)

    def contact_modify(self, org_id: int, user_id: int, contact_ids: list[int], modifiers: list[Modifier]):
        payload = {
            "org_id": org_id,
            "user_id": user_id,
            "contact_ids": contact_ids,
            "modifiers": [asdict(m) for m in modifiers],
        }

        return self._request("contact/modify", payload)

    def contact_search(
        self, org_id: int, group_id: int, query: str, sort: str, offset=0, exclude_ids=()
    ) -> SearchResults:
        payload = {
            "org_id": org_id,
            "group_id": group_id,
            "exclude_ids": exclude_ids,
            "query": query,
            "sort": sort,
            "offset": offset,
        }
        response = self._request("contact/search", payload)
        return SearchResults(
            query=response["query"],
            total=response["total"],
            contact_ids=response["contact_ids"],
            metadata=QueryMetadata(**response.get("metadata", {})),
        )

    def contact_urns(self, org_id: int, urns: list[str]):
        response = self._request("contact/urns", {"org_id": org_id, "urns": urns})
        return [URNResult(**ur) for ur in response["urns"]]

    def flow_change_language(self, flow, language):
        payload = {"flow": flow, "language": language}

        return self._request("flow/change_language", payload, encode_json=True)

    def flow_clone(self, flow, dependency_mapping):
        payload = {"flow": flow, "dependency_mapping": dependency_mapping}

        return self._request("flow/clone", payload)

    def flow_inspect(self, org_id, flow):
        payload = {"flow": flow}

        # can't do dependency checking during tests because mailroom can't see unit test data created in a transaction
        if not settings.TESTING:
            payload["org_id"] = org_id

        return self._request("flow/inspect", payload, encode_json=True)

    def flow_migrate(self, definition, to_version=None):
        """
        Migrates a flow definition to the specified spec version
        """
        from temba.flows.models import Flow

        if not to_version:  # pragma: no cover
            to_version = Flow.CURRENT_SPEC_VERSION

        return self._request("flow/migrate", {"flow": definition, "to_version": to_version}, encode_json=True)

    def flow_start_preview(self, org_id: int, flow_id: int, include: Inclusions, exclude: Exclusions) -> StartPreview:
        payload = {
            "org_id": org_id,
            "flow_id": flow_id,
            "include": asdict(include),
            "exclude": asdict(exclude),
        }

        response = self._request("flow/start_preview", payload, encode_json=True)
        return StartPreview(query=response["query"], total=response["total"])

    def msg_broadcast(
        self,
        org_id: int,
        user_id: int,
        translations: dict,
        base_language: str,
        group_ids: list,
        contact_ids: list,
        urns: list,
        query: str,
        node_uuid: str,
        optin_id: int,
        schedule: ScheduleSpec,
    ):
        payload = {
            "org_id": org_id,
            "user_id": user_id,
            "translations": translations,
            "base_language": base_language,
            "group_ids": group_ids,
            "contact_ids": contact_ids,
            "urns": urns,
            "query": query,
            "node_uuid": node_uuid,
            "optin_id": optin_id,
            "schedule": asdict(schedule) if schedule else None,
        }

        return self._request("msg/broadcast", payload, encode_json=True)

    def msg_broadcast_preview(self, org_id: int, include: Inclusions, exclude: Exclusions) -> BroadcastPreview:
        payload = {"org_id": org_id, "include": asdict(include), "exclude": asdict(exclude)}

        response = self._request("msg/broadcast_preview", payload, encode_json=True)
        return BroadcastPreview(query=response["query"], total=response["total"])

    def msg_handle(self, org_id: int, msg_ids: list):
        payload = {"org_id": org_id, "msg_ids": msg_ids}

        return self._request("msg/handle", payload)

    def msg_resend(self, org_id: int, msg_ids: list):
        payload = {"org_id": org_id, "msg_ids": msg_ids}

        return self._request("msg/resend", payload)

    def msg_send(self, org_id: int, user_id: int, contact_id: int, text: str, attachments: list[str], ticket_id: int):
        payload = {
            "org_id": org_id,
            "user_id": user_id,
            "contact_id": contact_id,
            "text": text,
            "attachments": attachments,
            "ticket_id": ticket_id,
        }

        return self._request("msg/send", payload)

    def po_export(self, org_id: int, flow_ids: list, language: str):
        payload = {"org_id": org_id, "flow_ids": flow_ids, "language": language}

        return self._request("po/export", payload)

    def po_import(self, org_id, flow_ids, language, po_data):
        payload = {"org_id": org_id, "flow_ids": flow_ids, "language": language}

        return self._request("po/import", payload, files={"po": po_data})

    def sim_start(self, payload):
        return self._request("sim/start", payload, encode_json=True)

    def sim_resume(self, payload):
        return self._request("sim/resume", payload, encode_json=True)

    def parse_query(self, org_id: int, query: str, parse_only: bool = False) -> ParsedQuery:
        payload = {"org_id": org_id, "query": query, "parse_only": parse_only}

        response = self._request("contact/parse_query", payload)
        return ParsedQuery(query=response["query"], metadata=QueryMetadata(**response.get("metadata", {})))

    def ticket_assign(self, org_id: int, user_id: int, ticket_ids: list, assignee_id: int):
        payload = {"org_id": org_id, "user_id": user_id, "ticket_ids": ticket_ids, "assignee_id": assignee_id}

        return self._request("ticket/assign", payload)

    def ticket_add_note(self, org_id: int, user_id: int, ticket_ids: list, note: str):
        payload = {"org_id": org_id, "user_id": user_id, "ticket_ids": ticket_ids, "note": note}

        return self._request("ticket/add_note", payload)

    def ticket_change_topic(self, org_id: int, user_id: int, ticket_ids: list, topic_id: int):
        payload = {"org_id": org_id, "user_id": user_id, "ticket_ids": ticket_ids, "topic_id": topic_id}

        return self._request("ticket/change_topic", payload)

    def ticket_close(self, org_id: int, user_id: int, ticket_ids: list, force: bool):
        payload = {"org_id": org_id, "user_id": user_id, "ticket_ids": ticket_ids, "force": force}

        return self._request("ticket/close", payload)

    def ticket_reopen(self, org_id, user_id, ticket_ids):
        payload = {"org_id": org_id, "user_id": user_id, "ticket_ids": ticket_ids}

        return self._request("ticket/reopen", payload)

    def _request(self, endpoint, payload=None, files=None, post=True, encode_json=False):
        if logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            logger.debug("=============== %s request ===============" % endpoint)
            logger.debug(json.dumps(payload, indent=2))
            logger.debug("=============== /%s request ===============" % endpoint)

        headers = self.headers.copy()
        if files:
            kwargs = dict(data=payload, files=files)
        elif encode_json:
            # do the JSON encoding ourselves - required when the json is something we've loaded with our decoder
            # which could contain non-standard types
            headers["Content-Type"] = "application/json"
            kwargs = dict(data=json.dumps(payload))
        else:
            kwargs = dict(json=payload)

        req_fn = requests.post if post else requests.get
        response = req_fn("%s/mr/%s" % (self.base_url, endpoint), headers=headers, **kwargs)

        if response.headers.get("Content-Type") == "application/json":
            resp_body = response.json()
        else:
            # not all endpoints return JSON, e.g. po file export
            resp_body = response.content

        if response.status_code == 422:
            error = resp_body["error"]
            domain, code = resp_body["code"].split(":")
            extra = resp_body.get("extra", {})

            if domain == "flow":
                raise FlowValidationException(error)
            elif domain == "query":
                raise QueryValidationException(error, code, extra)
            elif domain == "urn":
                raise URNValidationException(error, code, extra["index"])
            elif domain == "broadcast":
                raise EmptyBroadcastException()

        elif 400 <= response.status_code < 600:
            raise RequestException(endpoint, payload, response)

        return resp_body
