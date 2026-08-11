import { Notification, ObjectReference, User } from '../interfaces';
import { Events } from '../events/eventRenderers';
import type { StoreAsset } from '../store/Store';
import {
  PublicationHandler,
  SocketSubscription,
  subscribeToSocket
} from './SocketService';

/**
 * Typed access to our realtime topics. SocketService owns the shared
 * connection and per-channel fan-out; this module owns how topics map to
 * channel names, including the page identity (org and user uuids) needed to
 * address user-scoped channels, and what each topic publishes.
 *
 * The identity arrives via temba-store (hydrated from the page template), so
 * user-scoped subscriptions requested before the store mounts are queued and
 * activate when the context is set. On pages with no authenticated context
 * they simply never activate.
 *
 * Payload types below describe the wire, which is raw JSON - timestamps are
 * strings here even where the rendered equivalents in events.ts carry Dates.
 */

export interface RealtimeSubscription {
  unsubscribe(): void;
}

/** Anything published on any of our topics. */
export interface RealtimeEvent {
  type: string;
}

/**
 * org:<org-uuid> - workspace-wide state every component on the page shares.
 * An asset changed somewhere, so anything displaying it can update.
 */
export interface AssetChangedEvent extends RealtimeEvent {
  type: 'asset_changed';
  asset: StoreAsset;
}

export type OrganizationEvent = AssetChangedEvent;

/**
 * flow:<flow-uuid> - published once per committed sprint batch while a flow
 * is running. It carries no counts, it just says they moved: the editor reads
 * the current numbers over http when it sees one.
 */
export interface FlowActivityEvent extends RealtimeEvent {
  type: 'activity';
}

export type FlowEvent = FlowActivityEvent;

/**
 * history:<contact-uuid> and history:<contact-uuid>:<ticket-uuid> - the
 * engine's contact events (the payloads in events.ts, before their dates are
 * parsed) plus the ephemeral ones below, which are never persisted.
 */
export interface ContactHistoryEvent extends RealtimeEvent {
  uuid?: string;
  created_on?: string;
  _user?: User;
  // the rest of the payload varies by type. The contact-state events - the
  // ones we read fields off rather than hand straight to the renderers - are
  // typed below; events.ts describes the rendered shape of the others.
  // unknown rather than any, so reading a field nobody declared is a type
  // error at the point of use instead of silently spreading
  [key: string]: unknown;
}

/**
 * The events that change what a contact *is*, as opposed to recording
 * something that happened to them. These are the ones ContactWatch applies to
 * the contact it holds, so their payloads are what a server-side rename would
 * break.
 */
export interface ContactNameChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_NAME_CHANGED;
  name: string;
}

export interface ContactLanguageChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_LANGUAGE_CHANGED;
  language: string;
}

export interface ContactStatusChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_STATUS_CHANGED;
  status: string;
}

export interface ContactFlowChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_FLOW_CHANGED;
  flow: ObjectReference | null;
}

export interface ContactLastSeenChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_LAST_SEEN_CHANGED;
  last_seen_on: string;
}

export interface ContactFieldChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_FIELD_CHANGED;
  field: { key: string; name: string };
  // engine field values always carry text; typed representations are present
  // when the value parses as that type (see goflow's Value)
  value: { text: string; datetime?: string; number?: string } | null;
}

export interface ContactGroupsChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_GROUPS_CHANGED;
  groups_added?: ObjectReference[];
  groups_removed?: ObjectReference[];
}

export interface ContactURNsChangedEvent extends ContactHistoryEvent {
  type: Events.CONTACT_URNS_CHANGED;
  urns: string[];
}

export type ContactStateEvent =
  | ContactNameChangedEvent
  | ContactLanguageChangedEvent
  | ContactStatusChangedEvent
  | ContactFlowChangedEvent
  | ContactLastSeenChangedEvent
  | ContactFieldChangedEvent
  | ContactGroupsChangedEvent
  | ContactURNsChangedEvent;

/**
 * Published by agents as they compose, and echoed back to the publisher, so
 * consumers filter out their own by _user.
 */
export interface TypingEvent extends ContactHistoryEvent {
  type: Events.TYPING_STARTED | Events.TYPING_STOPPED;
  direction?: string;
  // whatsapp expresses typing as an operation on the contact's last incoming
  // message, so publications carry its external id when we have one
  msg_external_id?: string;
}

export interface RealtimeContext {
  org: string;
  user: string;
}

interface PendingSubscription {
  resolveChannel: (ctx: RealtimeContext) => string;
  onPublication: PublicationHandler;
  onSubscribed?: () => void;
  sub: SocketSubscription;
  cancelled: boolean;
}

let context: RealtimeContext = null;
const pending: PendingSubscription[] = [];

/**
 * Sets the page's realtime identity, flushing any subscriptions that were
 * waiting on it. Set once per page load - an org switch is a full page
 * load, so a real page never changes or clears its context. Passing null is
 * a full reset for tests: it discards the context AND any still-queued
 * subscriptions, so handles handed out before the reset never activate.
 * Returns the previous context.
 */
export const setRealtimeContext = (
  ctx: RealtimeContext | null
): RealtimeContext | null => {
  const previous = context;
  context = ctx;
  if (ctx) {
    while (pending.length > 0) {
      const p = pending.shift();
      if (!p.cancelled) {
        p.sub = subscribeToSocket(
          p.resolveChannel(ctx),
          p.onPublication,
          p.onSubscribed
        );
      }
    }
  } else {
    pending.length = 0;
  }
  return previous;
};

const subscribeWhenReady = (
  resolveChannel: (ctx: RealtimeContext) => string,
  onPublication: PublicationHandler,
  onSubscribed?: () => void
): RealtimeSubscription => {
  if (context) {
    return subscribeToSocket(
      resolveChannel(context),
      onPublication,
      onSubscribed
    );
  }

  const p: PendingSubscription = {
    resolveChannel,
    onPublication,
    onSubscribed,
    sub: null,
    cancelled: false
  };
  pending.push(p);
  return {
    unsubscribe: () => {
      p.cancelled = true;
      if (p.sub) {
        p.sub.unsubscribe();
        p.sub = null;
      }
    }
  };
};

/**
 * The current user's notifications in the current workspace. onSubscribed
 * fires on every (re)subscribe, including after reconnects, so subscribers
 * can catch up on anything missed while offline.
 */
export const subscribeToNotifications = (
  onNotification: (notification: Notification) => void,
  onSubscribed?: () => void
): RealtimeSubscription => {
  return subscribeWhenReady(
    (ctx) => `notifications:${ctx.org}:${ctx.user}`,
    (data) => onNotification(data as Notification),
    onSubscribed
  );
};

/**
 * Workspace-wide state changes shared by every component on the page.
 */
export const subscribeToOrganization = (
  onEvent: (event: OrganizationEvent) => void,
  onSubscribed?: () => void
): RealtimeSubscription => {
  return subscribeWhenReady(
    (ctx) => `org:${ctx.org}`,
    (data) => onEvent(data as OrganizationEvent),
    onSubscribed
  );
};

/**
 * Realtime events for a flow open in the editor. Needs no page context
 * because the flow UUID uniquely identifies the authorized channel.
 */
export const subscribeToFlow = (
  flow: string,
  onEvent: (event: FlowEvent) => void,
  onSubscribed?: () => void
): RealtimeSubscription => {
  return subscribeToSocket(
    `flow:${flow}`,
    (data) => onEvent(data as FlowEvent),
    onSubscribed
  );
};

/**
 * A contact's history events, or a ticket's detail events when a ticket is
 * given. Needs no page context so subscribes immediately.
 */
export const subscribeToContactHistory = (
  contact: string,
  ticket: string | null,
  onEvent: (event: ContactHistoryEvent) => void,
  onSubscribed?: () => void
): RealtimeSubscription => {
  return subscribeToSocket(
    ticket ? `history:${contact}:${ticket}` : `history:${contact}`,
    (data) => onEvent(data as ContactHistoryEvent),
    onSubscribed
  );
};
