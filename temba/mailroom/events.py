from collections import defaultdict
from datetime import datetime, timedelta

import iso8601

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from temba.channels.models import Channel, ChannelEvent
from temba.flows.models import FlowExit, FlowRun
from temba.ivr.models import Call
from temba.msgs.models import Msg, OptIn
from temba.orgs.models import Org
from temba.tickets.models import Ticket, TicketEvent, Topic
from temba.users.models import User
from temba.utils import dynamo


class Event:
    """
    Utility class for working with engine events.
    """

    # engine events
    TYPE_AIRTIME_TRANSFERRED = "airtime_transferred"
    TYPE_BROADCAST_CREATED = "broadcast_created"
    TYPE_CONTACT_FIELD_CHANGED = "contact_field_changed"
    TYPE_CONTACT_GROUPS_CHANGED = "contact_groups_changed"
    TYPE_CONTACT_LANGUAGE_CHANGED = "contact_language_changed"
    TYPE_CONTACT_NAME_CHANGED = "contact_name_changed"
    TYPE_CONTACT_URNS_CHANGED = "contact_urns_changed"
    TYPE_FLOW_ENTERED = "flow_entered"
    TYPE_IVR_CREATED = "ivr_created"
    TYPE_MSG_CREATED = "msg_created"
    TYPE_MSG_RECEIVED = "msg_received"
    TYPE_OPTIN_REQUESTED = "optin_requested"
    TYPE_TICKET_ASSIGNED = "ticket_assigned"
    TYPE_TICKET_CLOSED = "ticket_closed"
    TYPE_TICKET_NOTE_ADDED = "ticket_note_added"
    TYPE_TICKET_TOPIC_CHANGED = "ticket_topic_changed"
    TYPE_TICKET_OPENED = "ticket_opened"
    TYPE_TICKET_REOPENED = "ticket_reopened"

    # additional events
    TYPE_CALL_STARTED = "call_started"
    TYPE_CHANNEL_EVENT = "channel_event"
    TYPE_FLOW_EXITED = "flow_exited"

    ticket_event_types = {
        TicketEvent.TYPE_OPENED: TYPE_TICKET_OPENED,
        TicketEvent.TYPE_ASSIGNED: TYPE_TICKET_ASSIGNED,
        TicketEvent.TYPE_NOTE_ADDED: TYPE_TICKET_NOTE_ADDED,
        TicketEvent.TYPE_TOPIC_CHANGED: TYPE_TICKET_TOPIC_CHANGED,
        TicketEvent.TYPE_CLOSED: TYPE_TICKET_CLOSED,
        TicketEvent.TYPE_REOPENED: TYPE_TICKET_REOPENED,
    }

    # as we migrate event types over to DynamoDB:
    #  1. we start mailroom writing that type to DynamoDB
    #  2. we backfill existing events of that type from Postgres to DynamoDB
    #  3. we switch to reading that type from DynamoDB by adding it here
    dynamo_types = {
        TYPE_AIRTIME_TRANSFERRED,
        TYPE_CONTACT_FIELD_CHANGED,
        TYPE_CONTACT_GROUPS_CHANGED,
        TYPE_CONTACT_LANGUAGE_CHANGED,
        TYPE_CONTACT_NAME_CHANGED,
        TYPE_CONTACT_URNS_CHANGED,
    }

    @staticmethod
    def _get_key(contact, uuid: str) -> tuple[str, str]:
        return f"con#{contact.uuid}", f"evt#{uuid}"

    @classmethod
    def _from_item(cls, contact, item: dict) -> dict:
        assert item["OrgID"] == contact.org_id, "org ID mismatch for contact event"

        data = item.get("Data", {})
        if dataGZ := item.get("DataGZ"):
            data |= dynamo.load_jsongz(dataGZ)

        data["uuid"] = item["SK"][4:]  # remove "evt#" prefix
        return data

    @classmethod
    def get_by_contact(cls, contact, *, after: datetime, before: datetime, limit: int) -> list[dict]:
        """
        Eventually contact history will be paged by event UUIDs but for now we are given microsecond accuracy
        datetimes and have to infer approximate UUIDs and then filter the results to the given range.
        """
        if after >= before:  # otherwise DynamoDB blows up
            return []

        after_uuid = cls._time_to_uuid(after)
        before_uuid = cls._time_to_uuid(before + timedelta(milliseconds=1))

        pk, before_sk = cls._get_key(contact, before_uuid)
        after_sk = f"evt#{after_uuid}"

        events = []
        next_before_sk = None
        num_fetches = 0

        while True:
            assert num_fetches < 100, "too many fetches for contact history"

            kwargs = dict(
                KeyConditionExpression="PK = :pk AND SK BETWEEN :after_sk AND :before_sk",
                ExpressionAttributeValues={":pk": pk, ":after_sk": after_sk, ":before_sk": before_sk},
                ScanIndexForward=False,
                Limit=50,
                Select="ALL_ATTRIBUTES",
            )

            if next_before_sk:  # pragma: no cover
                kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": next_before_sk}

            response = dynamo.HISTORY.query(**kwargs)
            num_fetches += 1

            for item in response.get("Items", []):
                event = cls._from_item(contact, item)
                event_time = iso8601.parse_date(event["created_on"])

                if event_time >= after and event_time < before and event["type"] in cls.dynamo_types:
                    events.append(event)

                    if len(events) == limit:
                        return events

            next_before_sk = response.get("LastEvaluatedKey", {}).get("SK")
            if not next_before_sk:
                break

        return events

    @staticmethod
    def _time_to_uuid(dt: datetime) -> str:
        ts_millis = int(dt.timestamp() * 1_000)
        ts_as_hex = "%012x" % (ts_millis & 0xFFFFFFFFFFFF)
        return f"{ts_as_hex[:8]}-{ts_as_hex[8:12]}-7000-0000-000000000000"

    @classmethod
    def from_history_item(cls, org: Org, user: User, item) -> dict:
        if isinstance(item, dict):  # already an event
            return item

        renderer = event_renderers.get(type(item))
        assert renderer is not None, f"unsupported history item of type {type(item)}"

        return renderer(org, user, item)

    @classmethod
    def from_msg(cls, org: Org, user: User, obj: Msg) -> dict:
        """
        Reconstructs an engine event from a msg instance. Properties which aren't part of regular events are prefixed
        with an underscore.
        """

        obj_age = timezone.now() - obj.created_on

        logs_url = None
        if obj.channel and obj_age < settings.RETENTION_PERIODS["channellog"]:
            logs_url = _url_for_user(
                org,
                user,
                "channels.channel_logs_read",
                args=[obj.channel.uuid, "msg", obj.id],
                perm="channels.channel_logs",
            )

        if obj.direction == Msg.DIRECTION_IN:
            return {
                "uuid": str(obj.uuid),
                "type": cls.TYPE_MSG_RECEIVED,
                "created_on": get_event_time(obj).isoformat(),
                "msg": _msg_in(obj),
                # additional properties
                "msg_type": Msg.TYPE_VOICE if obj.msg_type == Msg.TYPE_VOICE else Msg.TYPE_TEXT,
                "visibility": obj.visibility,
                "logs_url": logs_url,
            }
        elif obj.broadcast and obj.broadcast.get_message_count() > 1:
            return {
                "uuid": str(obj.uuid),
                "type": cls.TYPE_BROADCAST_CREATED,
                "created_on": get_event_time(obj).isoformat(),
                "translations": obj.broadcast.translations,
                "base_language": obj.broadcast.base_language,
                # additional properties
                "created_by": _user(obj.broadcast.created_by) if obj.broadcast.created_by else None,
                "msg": _msg_out(obj),
                "optin": _optin(obj.optin) if obj.optin else None,
                "status": obj.status,
                "recipient_count": obj.broadcast.get_message_count(),
                "logs_url": logs_url,
            }
        else:
            created_by = obj.broadcast.created_by if obj.broadcast else obj.created_by

            if obj.msg_type == Msg.TYPE_VOICE:
                msg_event = {
                    "uuid": str(obj.uuid),
                    "type": cls.TYPE_IVR_CREATED,
                    "created_on": get_event_time(obj).isoformat(),
                    "msg": _msg_out(obj),
                }
            elif obj.msg_type == Msg.TYPE_OPTIN and obj.optin:
                msg_event = {
                    "uuid": str(obj.uuid),
                    "type": cls.TYPE_OPTIN_REQUESTED,
                    "created_on": get_event_time(obj).isoformat(),
                    "optin": _optin(obj.optin),
                    "channel": _channel(obj.channel),
                    "urn": str(obj.contact_urn),
                }
            else:
                msg_event = {
                    "uuid": str(obj.uuid),
                    "type": cls.TYPE_MSG_CREATED,
                    "created_on": get_event_time(obj).isoformat(),
                    "msg": _msg_out(obj),
                    "optin": _optin(obj.optin) if obj.optin else None,
                }

            # add additional properties
            msg_event["created_by"] = _user(created_by) if created_by else None
            msg_event["status"] = obj.status
            msg_event["logs_url"] = logs_url

            if obj.status == Msg.STATUS_FAILED:
                msg_event["failed_reason"] = obj.failed_reason
                msg_event["failed_reason_display"] = obj.get_failed_reason_display()

            return msg_event

    @classmethod
    def from_flow_run(cls, org: Org, user: User, obj: FlowRun) -> dict:
        logs_url = (
            _url_for_user(org, user, "flows.flowsession_json", args=[obj.session_uuid]) if obj.session_uuid else None
        )

        return {
            "type": cls.TYPE_FLOW_ENTERED,
            "created_on": get_event_time(obj).isoformat(),
            "flow": {"uuid": str(obj.flow.uuid), "name": obj.flow.name},
            "logs_url": logs_url,
        }

    @classmethod
    def from_flow_exit(cls, org: Org, user: User, obj: FlowExit) -> dict:
        return {
            "type": cls.TYPE_FLOW_EXITED,
            "created_on": get_event_time(obj).isoformat(),
            "flow": {"uuid": str(obj.run.flow.uuid), "name": obj.run.flow.name},
            # additional properties
            "status": obj.run.status,
        }

    @classmethod
    def from_ivr_call(cls, org: Org, user: User, obj: Call) -> dict:
        obj_age = timezone.now() - obj.created_on

        logs_url = None
        if obj_age < settings.RETENTION_PERIODS["channellog"]:
            logs_url = _url_for_user(
                org,
                user,
                "channels.channel_logs_read",
                args=[obj.channel.uuid, "call", obj.id],
                perm="channels.channel_logs",
            )

        return {
            "type": cls.TYPE_CALL_STARTED,
            "created_on": get_event_time(obj).isoformat(),
            "status": obj.status,
            "status_display": obj.status_display,
            "logs_url": logs_url,
        }

    @classmethod
    def from_ticket_event(cls, org: Org, user: User, obj: TicketEvent) -> dict:
        ticket = obj.ticket
        return {
            "type": cls.ticket_event_types[obj.event_type],
            "note": obj.note,
            "topic": _topic(obj.topic) if obj.topic else None,
            "assignee": _user(obj.assignee) if obj.assignee else None,
            "ticket": {
                "uuid": str(ticket.uuid),
                "opened_on": ticket.opened_on.isoformat(),
                "closed_on": ticket.closed_on.isoformat() if ticket.closed_on else None,
                "topic": _topic(ticket.topic) if ticket.topic else None,
                "status": ticket.status,
            },
            "created_on": get_event_time(obj).isoformat(),
            "created_by": _user(obj.created_by) if obj.created_by else None,
        }

    @classmethod
    def from_channel_event(cls, org: Org, user: User, obj: ChannelEvent) -> dict:
        extra = obj.extra or {}
        ch_event = {"type": obj.event_type, "channel": _channel(obj.channel)}

        if obj.event_type in ChannelEvent.CALL_TYPES:
            ch_event["duration"] = extra.get("duration")
        elif obj.event_type in (ChannelEvent.TYPE_OPTIN, ChannelEvent.TYPE_OPTOUT):
            ch_event["optin"] = _optin(obj.optin) if obj.optin else None

        return {
            "uuid": str(obj.uuid),
            "type": cls.TYPE_CHANNEL_EVENT,
            "created_on": get_event_time(obj).isoformat(),
            "event": ch_event,
            "channel_event_type": obj.event_type,  # deprecated
            "duration": extra.get("duration"),  # deprecated
        }


def _url_for_user(org: Org, user: User, view_name: str, args: list, perm: str = None) -> str:
    allowed = user.has_org_perm(org, perm or view_name) or user.is_staff

    return reverse(view_name, args=args) if allowed else None


def _msg_in(obj) -> dict:
    d = _base_msg(obj)

    if obj.external_id:
        d["external_id"] = obj.external_id

    return d


def _msg_out(obj) -> dict:
    d = _base_msg(obj)

    if obj.quick_replies:
        d["quick_replies"] = obj.quick_replies

    return d


def _base_msg(obj) -> dict:
    redact = obj.visibility in (Msg.VISIBILITY_DELETED_BY_USER, Msg.VISIBILITY_DELETED_BY_SENDER)
    d = {
        "id": obj.id,
        "urn": str(obj.contact_urn) if obj.contact_urn else None,
        "channel": _channel(obj.channel) if obj.channel else None,
        "text": obj.text if not redact else "",
    }
    if obj.attachments:
        d["attachments"] = obj.attachments if not redact else []

    return d


def _user(user: User) -> dict:
    return {"id": user.id, "first_name": user.first_name, "last_name": user.last_name, "email": user.email}


def _channel(channel: Channel) -> dict:
    return {"uuid": str(channel.uuid), "name": channel.name}


def _topic(topic: Topic) -> dict:
    return {"uuid": str(topic.uuid), "name": topic.name}


def _optin(optin: OptIn) -> dict:
    return {"uuid": str(optin.uuid), "name": optin.name}


# map of history item types to methods to render them as events
event_renderers = {
    ChannelEvent: Event.from_channel_event,
    FlowExit: Event.from_flow_exit,
    FlowRun: Event.from_flow_run,
    Call: Event.from_ivr_call,
    Msg: Event.from_msg,
    TicketEvent: Event.from_ticket_event,
}

# map of history item types to a callable which can extract the event time from that type
event_time = defaultdict(lambda: lambda i: i.created_on)
event_time.update(
    {
        dict: lambda e: iso8601.parse_date(e["created_on"]),
        FlowExit: lambda e: e.run.exited_on,
        Ticket: lambda e: e.closed_on,
    },
)


def get_event_time(item) -> datetime:
    """
    Extracts the event time from a history item
    """
    return event_time[type(item)](item)
