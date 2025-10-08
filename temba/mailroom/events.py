from datetime import datetime, timedelta
from uuid import UUID

import iso8601

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from temba.channels.models import Channel
from temba.msgs.models import Msg, OptIn
from temba.orgs.models import Org
from temba.users.models import User
from temba.utils import dynamo


class Event:
    """
    Utility class for working with engine events.
    """

    # engine events
    TYPE_AIRTIME_TRANSFERRED = "airtime_transferred"
    TYPE_BROADCAST_CREATED = "broadcast_created"
    TYPE_CALL_CREATED = "call_created"
    TYPE_CALL_MISSED = "call_missed"
    TYPE_CALL_RECEIVED = "call_received"
    TYPE_CHAT_STARTED = "chat_started"
    TYPE_CONTACT_FIELD_CHANGED = "contact_field_changed"
    TYPE_CONTACT_GROUPS_CHANGED = "contact_groups_changed"
    TYPE_CONTACT_LANGUAGE_CHANGED = "contact_language_changed"
    TYPE_CONTACT_NAME_CHANGED = "contact_name_changed"
    TYPE_CONTACT_STATUS_CHANGED = "contact_status_changed"
    TYPE_CONTACT_URNS_CHANGED = "contact_urns_changed"
    TYPE_IVR_CREATED = "ivr_created"
    TYPE_MSG_CREATED = "msg_created"
    TYPE_MSG_RECEIVED = "msg_received"
    TYPE_OPTIN_REQUESTED = "optin_requested"
    TYPE_OPTIN_STARTED = "optin_started"
    TYPE_OPTIN_STOPPED = "optin_stopped"
    TYPE_RUN_STARTED = "run_started"
    TYPE_RUN_ENDED = "run_ended"
    TYPE_TICKET_ASSIGNED = "ticket_assignee_changed"
    TYPE_TICKET_CLOSED = "ticket_closed"
    TYPE_TICKET_NOTE_ADDED = "ticket_note_added"
    TYPE_TICKET_OPENED = "ticket_opened"
    TYPE_TICKET_REOPENED = "ticket_reopened"
    TYPE_TICKET_TOPIC_CHANGED = "ticket_topic_changed"

    # as we migrate event types over to DynamoDB:
    #  1. we start mailroom writing that type to DynamoDB
    #  2. we backfill existing events of that type from Postgres to DynamoDB
    #  3. we switch to reading that type from DynamoDB by adding it here
    dynamo_types = {
        TYPE_AIRTIME_TRANSFERRED,
        TYPE_CALL_CREATED,
        TYPE_CALL_MISSED,
        TYPE_CALL_RECEIVED,
        TYPE_CHAT_STARTED,
        TYPE_CONTACT_FIELD_CHANGED,
        TYPE_CONTACT_GROUPS_CHANGED,
        TYPE_CONTACT_LANGUAGE_CHANGED,
        TYPE_CONTACT_NAME_CHANGED,
        TYPE_CONTACT_STATUS_CHANGED,
        TYPE_CONTACT_URNS_CHANGED,
        TYPE_OPTIN_REQUESTED,
        TYPE_OPTIN_STARTED,
        TYPE_OPTIN_STOPPED,
        TYPE_RUN_STARTED,
        TYPE_RUN_ENDED,
        TYPE_TICKET_ASSIGNED,
        TYPE_TICKET_CLOSED,
        TYPE_TICKET_NOTE_ADDED,
        TYPE_TICKET_OPENED,
        TYPE_TICKET_REOPENED,
        TYPE_TICKET_TOPIC_CHANGED,
    }

    basic_ticket_types = {TYPE_TICKET_CLOSED, TYPE_TICKET_OPENED, TYPE_TICKET_REOPENED}
    all_ticket_types = basic_ticket_types | {TYPE_TICKET_ASSIGNED, TYPE_TICKET_NOTE_ADDED, TYPE_TICKET_TOPIC_CHANGED}

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
    def _tag_from_item(cls, contact, item: dict) -> dict:
        assert item["OrgID"] == contact.org_id, "org ID mismatch for contact event tag"

        return {"event_uuid": item["SK"][4:40], "tag": item["SK"][40:], "data": item.get("Data", {})}

    @classmethod
    def get_by_contact(cls, contact, *, after: datetime, before: datetime, ticket_uuid: UUID, limit: int) -> list[dict]:
        """
        Eventually contact history will be paged by event UUIDs but for now we are given microsecond accuracy
        datetimes and have to infer approximate UUIDs and then filter the results to the given range.
        """
        if after >= before:  # otherwise DynamoDB blows up
            return []

        events, tags = cls._get_raw(contact, after=after, before=before, ticket_uuid=ticket_uuid, limit=limit)

        return cls._refresh_events(contact.org, events)

    @classmethod
    def _get_raw(
        cls, contact, *, after: datetime, before: datetime, ticket_uuid: UUID, limit: int
    ) -> tuple[list[dict], list[dict]]:
        """
        Eventually contact history will be paged by event UUIDs but for now we are given microsecond accuracy
        datetimes and have to infer approximate UUIDs and then filter the results to the given range.
        """

        after_uuid = cls._time_to_uuid(after)
        before_uuid = cls._time_to_uuid(before + timedelta(milliseconds=1))

        pk, before_sk = cls._get_key(contact, before_uuid)
        after_sk = f"evt#{after_uuid}"

        events, tags = [], []

        def _item(item: dict) -> bool:
            if item["SK"].count("#") == 1:  # item is an event
                event = cls._from_item(contact, item)
                event_time = iso8601.parse_date(event["created_on"])

                if event_time >= after and event_time < before and cls._include_event(event, ticket_uuid):
                    events.append(event)

                return len(events) < limit
            else:  # item is a tag
                tags.append(cls._tag_from_item(contact, item))
                # keep going we always end with a complete event
                return True

        cls._get_history_items(pk, after_sk=after_sk, before_sk=before_sk, limit=limit, callback=_item)

        return events, tags

    @classmethod
    def _get_history_items(cls, pk: str, *, after_sk: str, before_sk: str, limit: int, callback):
        num_fetches = 0
        next_before_sk = None

        while True:
            assert num_fetches < 100, "too many fetches for history"

            # TODO because for now we skip over some items, if limit is 1 we could end up making multiple fetches to
            # get to an item that isn't skipped.. so always fetch at least 20 items
            kwargs = dict(
                KeyConditionExpression="PK = :pk AND SK BETWEEN :after_sk AND :before_sk",
                ExpressionAttributeValues={":pk": pk, ":after_sk": after_sk, ":before_sk": before_sk},
                ScanIndexForward=False,
                Limit=max(limit, 20),
                Select="ALL_ATTRIBUTES",
            )

            if next_before_sk:  # pragma: no cover
                kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": next_before_sk}

            response = dynamo.HISTORY.query(**kwargs)
            num_fetches += 1

            for item in response.get("Items", []):
                if not callback(item):
                    return

            next_before_sk = response.get("LastEvaluatedKey", {}).get("SK")
            if not next_before_sk:
                return

    @classmethod
    def _include_event(cls, event, ticket_uuid) -> bool:
        if event["type"] in cls.all_ticket_types:
            if ticket_uuid:
                # if we have a ticket this is for the ticket UI, so we want *all* events for *only* that ticket
                event_ticket_uuid = event.get("ticket_uuid", event.get("ticket", {}).get("uuid"))
                return event_ticket_uuid == str(ticket_uuid)
            else:
                # if not then this for the contact read page so only show ticket opened/closed/reopened events
                return event["type"] in cls.basic_ticket_types

        return event["type"] in cls.dynamo_types

    @classmethod
    def _refresh_events(cls, org, events: list[dict]) -> list[dict]:
        """
        Refreshes a list of events in place with up to date information from the database. This probably moves to
        mailroom at some point.
        """

        user_uuids = {event["_user"]["uuid"] for event in events if event.get("_user")}
        users_by_uuid = {str(u.uuid): u for u in org.get_users().filter(uuid__in=user_uuids)}

        for event in events:
            if "_user" in event and event["_user"]:
                if user := users_by_uuid.get(event["_user"]["uuid"]):
                    event["_user"].update({"name": user.first_name, "avatar": user.avatar.url if user.avatar else None})
                else:
                    event["_user"] = None  # user no longer exists

        return events

    @staticmethod
    def _time_to_uuid(dt: datetime) -> str:
        ts_millis = int(dt.timestamp() * 1_000)
        ts_as_hex = "%012x" % (ts_millis & 0xFFFFFFFFFFFF)
        return f"{ts_as_hex[:8]}-{ts_as_hex[8:12]}-7000-0000-000000000000"

    @classmethod
    def from_history_item(cls, org: Org, user: User, item) -> dict:
        if isinstance(item, Msg):
            return Event.from_msg(org, user, item)

        return item  # already an event dict

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
                args=[obj.channel.uuid, "msg", obj.uuid],
                perm="channels.channel_logs",
            )

        if obj.direction == Msg.DIRECTION_IN:
            event = {
                "uuid": str(obj.uuid),
                "type": cls.TYPE_MSG_RECEIVED,
                "created_on": get_event_time(obj).isoformat(),
                "msg": _msg_in(obj),
                # additional properties
                "_logs_url": logs_url,
            }

            if obj.visibility == Msg.VISIBILITY_DELETED_BY_SENDER:
                event["_deleted"] = {"deleted_by": "contact", "deleted_on": obj.modified_on.isoformat()}
            elif obj.visibility == Msg.VISIBILITY_DELETED_BY_USER:
                event["_deleted"] = {"deleted_by": "user", "deleted_on": obj.modified_on.isoformat()}

            return event
        else:
            if obj.msg_type == Msg.TYPE_VOICE:
                event = {
                    "uuid": str(obj.uuid),
                    "type": cls.TYPE_IVR_CREATED,
                    "created_on": get_event_time(obj).isoformat(),
                    "msg": _msg_out(obj),
                }
            else:
                event = {
                    "uuid": str(obj.uuid),
                    "type": cls.TYPE_MSG_CREATED,
                    "created_on": get_event_time(obj).isoformat(),
                    "msg": _msg_out(obj),
                    "optin": _optin(obj.optin) if obj.optin else None,
                }
                if obj.broadcast:
                    event["broadcast_uuid"] = str(obj.broadcast.uuid)

                if obj.status in (
                    Msg.STATUS_SENT,
                    Msg.STATUS_DELIVERED,
                    Msg.STATUS_READ,
                    Msg.STATUS_ERRORED,
                    Msg.STATUS_FAILED,
                ):
                    event["_statuses"] = {obj.status: {"changed_on": obj.modified_on.isoformat()}}
                    if obj.status == Msg.STATUS_FAILED:
                        event["_statuses"][Msg.STATUS_FAILED]["reason"] = obj.get_failed_reason_display()

            # add additional properties
            event["_user"] = _user(obj.created_by) if obj.created_by else None
            event["_status"] = obj.status
            event["_logs_url"] = logs_url

            if obj.status == Msg.STATUS_FAILED:
                event["_failed_reason"] = obj.get_failed_reason_display()

            return event


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
        "urn": str(obj.contact_urn) if obj.contact_urn else None,
        "channel": _channel(obj.channel) if obj.channel else None,
        "text": obj.text if not redact else "",
    }
    if obj.attachments:
        d["attachments"] = obj.attachments if not redact else []

    return d


def _user(user: User) -> dict:
    return {"uuid": str(user.uuid), "name": user.name, "avatar": user.avatar.url if user.avatar else None}


def _channel(channel: Channel) -> dict:
    return {"uuid": str(channel.uuid), "name": channel.name}


def _optin(optin: OptIn) -> dict:
    return {"uuid": str(optin.uuid), "name": optin.name}


def get_event_time(item) -> datetime:
    """
    Extracts the event time from a history item
    """

    if isinstance(item, Msg):
        return item.created_on

    return iso8601.parse_date(item["created_on"])
