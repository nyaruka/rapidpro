from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import iso8601

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from temba.msgs.models import Msg
from temba.orgs.models import Org
from temba.users.models import User
from temba.utils import dynamo

msg_tag_statuses = {
    Msg.STATUS_WIRED: "wired",
    Msg.STATUS_SENT: "sent",
    Msg.STATUS_DELIVERED: "delivered",
    Msg.STATUS_READ: "read",
    Msg.STATUS_ERRORED: "errored",
    Msg.STATUS_FAILED: "failed",
}

# Msg.failed_reason codes that are stored on events as "unsendable_reason"
failed_reason_to_unsendable = {
    Msg.FAILED_NO_DESTINATION: "no_route",
    Msg.FAILED_CONTACT: "contact_blocked",
    Msg.FAILED_SUSPENDED: "org_suspended",
    Msg.FAILED_LOOPING: "looping",
}

# Msg.failed_reason codes that are stored as "reason" on status tags
failed_reason_to_tag_reason = {
    Msg.FAILED_ERROR_LIMIT: "error_limit",
    Msg.FAILED_TOO_OLD: "too_old",
    Msg.FAILED_CHANNEL_REMOVED: "channel_removed",
}


@dataclass
class EventTag:
    event_uuid: str
    tag: str
    data: dict


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
    def _tag_from_item(cls, contact, item: dict) -> EventTag:
        assert item["OrgID"] == contact.org_id, "org ID mismatch for contact event tag"

        return EventTag(event_uuid=item["SK"][4:40], tag=item["SK"][41:], data=item.get("Data", {}))

    @classmethod
    def get_by_contact(
        cls, contact, user, *, after: datetime, before: datetime, ticket_uuid: UUID, limit: int
    ) -> list[dict]:
        """
        Eventually contact history will be paged by event UUIDs but for now we are given microsecond accuracy
        datetimes and have to infer approximate UUIDs and then filter the results to the given range.
        """
        if after >= before:  # otherwise DynamoDB blows up
            return []

        events, tags = cls._get_raw(contact, after=after, before=before, ticket_uuid=ticket_uuid, limit=limit)

        # inject tags into their corresponding events
        events_by_uuid = {event["uuid"]: event for event in events}
        for tag in tags:
            if event := events_by_uuid.get(tag.event_uuid):
                if tag.tag == "del":
                    event["_deleted"] = tag.data
                elif tag.tag == "sts":
                    event["_status"] = tag.data

        return cls._refresh_events(contact.org, user, events)

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

            # Because we skip over some items (e.g. when viewing a ticket), if limit is 1 we could end up making
            # multiple fetches to get to an item that isn't skipped.. so always fetch at least 10 items
            kwargs = dict(
                KeyConditionExpression="PK = :pk AND SK BETWEEN :after_sk AND :before_sk",
                ExpressionAttributeValues={":pk": pk, ":after_sk": after_sk, ":before_sk": before_sk},
                ScanIndexForward=False,
                Limit=max(limit, 10),
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

        return True

    @classmethod
    def _refresh_events(cls, org, user: User, events: list[dict]) -> list[dict]:
        """
        Refreshes a list of events in place with up to date information from the database.
        """

        user_uuids = {event["_user"]["uuid"] for event in events if event.get("_user")}
        users_by_uuid = {str(u.uuid): u for u in org.get_users().filter(uuid__in=user_uuids)}

        # TODO build a more generic mechanism for refreshing all references to things like users, flows.. or put that
        # somewhere else entirely?
        for event in events:
            if "_user" in event and event["_user"]:
                if user := users_by_uuid.get(event["_user"]["uuid"]):
                    event["_user"].update({"name": user.first_name, "avatar": user.avatar.url if user.avatar else None})
                else:
                    event["_user"] = None  # user no longer exists

        # inject log URLs for message events
        for event in events:
            if event["type"] in [cls.TYPE_MSG_CREATED, cls.TYPE_MSG_RECEIVED, cls.TYPE_IVR_CREATED]:
                if channel := event["msg"].get("channel"):
                    evt_age = timezone.now() - iso8601.parse_date(event["created_on"])
                    if evt_age < settings.RETENTION_PERIODS["channellog"]:
                        logs_url = _url_for_user(
                            org,
                            user,
                            "channels.channel_logs_read",
                            args=[channel["uuid"], "msg", event["uuid"]],
                            perm="channels.channel_logs",
                        )
                        if logs_url:
                            event["_logs_url"] = logs_url

        return events

    @staticmethod
    def _time_to_uuid(dt: datetime) -> str:
        ts_millis = int(dt.timestamp() * 1_000)
        ts_as_hex = "%012x" % (ts_millis & 0xFFFFFFFFFFFF)
        return f"{ts_as_hex[:8]}-{ts_as_hex[8:12]}-7000-0000-000000000000"


def _url_for_user(org: Org, user: User, view_name: str, args: list, perm: str = None) -> str:
    allowed = user.has_org_perm(org, perm or view_name) or user.is_staff

    return reverse(view_name, args=args) if allowed else None
