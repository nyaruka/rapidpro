import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import {
  CustomEventType,
  ObjectReference,
  ScheduledEvent,
  ScheduledEventType
} from '../interfaces';
import { EndpointMonitorElement } from '../store/EndpointMonitorElement';
import { Icon } from '../Icons';

interface EventsResponse {
  now: string;
  campaigns: ObjectReference[];
  future_count: number;
  future: ScheduledEvent[];
  past: ScheduledEvent[];
  next_before: string | null;
  next_after: string | null;
}

// four distinct primary hues assigned per campaign - chosen for maximum spread
// so the first handful of campaigns read clearly apart. Purple is reserved for
// broadcasts and green is reserved for triggers (matches the flow pill hue).
// The trailing four entries are darker shades of the primaries for the rare
// case where a contact belongs to more than four campaigns at once.
const CAMPAIGN_COLORS = [
  '#1a86d0', // blue
  '#e8843f', // orange
  '#ec407a', // pink
  '#2bb2a6', // teal
  '#0a5290', // deep blue
  '#a25320', // deep orange
  '#a02153', // deep pink
  '#176a61' // deep teal
];

// shared "broadcast purple" used elsewhere for broadcasts
const BROADCAST_COLOR = '#8e5ea7';

// triggers use the same green as the flow pill
const TRIGGER_COLOR = '#16a34a';

export class ContactTimeline extends EndpointMonitorElement {
  @property({ type: String })
  contact: string;

  @property({ type: Object, attribute: false })
  data: EventsResponse;

  @property({ type: String })
  lang_now = 'Now';

  @property({ type: String })
  lang_show_older = 'Show older events';

  @property({ type: String })
  lang_show_more = 'Show more upcoming events';

  @property({ type: String })
  lang_more = 'Show more';

  @property({ type: String })
  lang_campaigns_label = 'Campaigns';

  @property({ type: String })
  lang_empty = 'No upcoming events';

  @property({ type: String })
  lang_empty_help =
    'Events appear here when a contact joins a campaign. Scheduled flows and messages will also show up here.';

  @property({ type: String })
  lang_campaigns_link = 'View campaigns';

  @property({ type: String })
  lang_projected_info =
    'This is a projected timeline based on current schedules. Past entries may not reflect what actually happened, and upcoming entries are limited to the next year.';

  // older past events accumulated through pagination
  @state()
  private olderEvents: ScheduledEvent[] = [];

  // further-upcoming events accumulated through pagination
  @state()
  private newerEvents: ScheduledEvent[] = [];

  // cursor for paging further back, null when there's nothing older
  @state()
  private nextBefore: string | null = null;

  // cursor for paging further forward, null when there's nothing further out
  @state()
  private nextAfter: string | null = null;

  @state()
  private loadingMore = false;

  @state()
  private loadingMoreFuture = false;

  // stable campaign uuid -> color assignments
  private campaignColors: { [uuid: string]: string } = {};

  static get styles() {
    return css`
      :host {
        display: block;
      }

      /* empty state follows the list design system: centered icon, a short
         title, muted explanatory copy, and a single call-to-action link */
      .empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        /* a host card sets --empty-padding to compact this treatment —
           the default suits a full-height tab pane */
        padding: var(--empty-padding, 7em 1em 4em);
        color: var(--text-color);
      }

      .empty temba-icon {
        margin-bottom: 0.75em;
        --icon-color: var(--text-3, #7b8593);
      }

      /* the icon / blurb / link around the title — a host card hides
         these so the empty card is just the stylized message */
      .empty-extras {
        display: var(--empty-extras-display, contents);
      }

      .empty-title {
        font-weight: 600;
        margin-bottom: 0.4em;
        font-size: var(--empty-title-size, inherit);
        color: var(--empty-title-color, inherit);
      }

      .empty-help {
        font-size: 0.875em;
        line-height: 1.5;
        max-width: 22em;
        margin-bottom: 1em;
        color: var(--text-3, #7b8593);
      }

      .empty-link {
        font-size: 0.875em;
        font-weight: 500;
        color: var(--color-link-primary);
        text-decoration: none;
      }

      .empty-link:hover {
        text-decoration: underline;
      }

      /* row of campaign pills the contact is currently a member of */
      .campaigns {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4em;
        padding: 0 0.5em 0.5em;
      }

      .campaigns-label {
        font-size: 0.75em;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-color);
        opacity: 0.55;
        margin-right: 0.25em;
      }

      /* each pill is colored with its campaign's hue - background, border
         and text all derived from --pill-hue. clickable links to the
         campaign's read page */
      .campaign-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78em;
        line-height: 1.5;
        padding: 0.05em 0.65em;
        border-radius: 999px;
        white-space: nowrap;
        /* plain bg / neutral border for browsers without color-mix();
           the hue-tinted versions live in the @supports block below */
        background: var(--color-widget-bg, #fff);
        border: 1px solid var(--pill-hue);
        color: var(--pill-hue);
        cursor: pointer;
        transition: background 100ms ease-in-out;
      }

      @supports (color: color-mix(in srgb, red, red)) {
        .campaign-pill {
          background: color-mix(
            in srgb,
            var(--pill-hue) 12%,
            var(--color-widget-bg, #fff)
          );
          border: 1px solid
            color-mix(
              in srgb,
              var(--pill-hue) 25%,
              var(--color-widget-bg, #fff)
            );
        }
        .campaign-pill:hover {
          background: color-mix(
            in srgb,
            var(--pill-hue) 22%,
            var(--color-widget-bg, #fff)
          );
        }
      }

      .campaign-pill:focus-visible {
        outline: 2px solid var(--pill-hue);
        outline-offset: 1px;
      }

      /* status-badge dot leading each campaign pill, in the same hue */
      .campaign-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--pill-hue);
      }

      .timeline {
        display: flex;
        flex-direction: column;
        padding: 0.5em 0;
      }

      .row {
        display: flex;
        align-items: stretch;
      }

      /* relative time, vertically centered on its dot. mute via color
         (not opacity) so the hovered date tooltip renders at full alpha
         and doesn't share a stacking context with the column */
      .time {
        width: 7em;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 0.65em;
        font-size: 0.8em;
        color: var(--text-3, #7b8593);
        white-space: nowrap;
      }

      .time temba-tip {
        cursor: default;
      }

      /* the subway rail */
      .track {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 1.75em;
        flex-shrink: 0;
      }

      .line {
        width: 2px;
        flex: 1;
        background: var(--color-borders, rgba(0, 0, 0, 0.12));
      }

      .line.hidden {
        background: transparent;
      }

      .dot {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        box-sizing: border-box;
        flex-shrink: 0;
        z-index: 1;
        /* same border on past and future - only the fill differs */
        border: 2px solid var(--dot-color);
        display: flex;
        align-items: center;
        justify-content: center;
        /* icons inside the dot take the dot's hue */
        --icon-color: var(--dot-color);
      }

      /* past events are filled with a lighter tint of the same hue and keep
         the solid border - they're settled, whether real or projected.
         Plain widget bg first for browsers without color-mix(). */
      .dot.past {
        background: var(--color-widget-bg, #fff);
      }

      /* future events haven't occurred yet - signal that with a dotted
         border and the faintest tint of the hue inside */
      .dot.future {
        border-style: dotted;
        background: var(--color-widget-bg, #fff);
      }

      @supports (color: color-mix(in srgb, red, red)) {
        .dot.past {
          background: color-mix(
            in srgb,
            var(--dot-color) 25%,
            var(--color-widget-bg, #fff)
          );
        }
        .dot.future {
          background: color-mix(
            in srgb,
            var(--dot-color) 8%,
            var(--color-widget-bg, #fff)
          );
        }
      }

      /* the now dot and label both paint with the SPA content background
         color - they look transparent but actually mask the rail and divider
         behind them, so the "Now" marker reads as a clean break */
      .dot.now {
        border: 2px solid var(--border-strong, #9ca3af);
        background: var(--color-widget-bg, #fff);
      }

      /* round button on the rail that pages further back / forward when
         clicked - up arrow above the past, down arrow below the future */
      .pager-dot {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        box-sizing: border-box;
        border: 2px solid var(--border-strong, #9ca3af);
        background: var(--color-widget-bg, #fff);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        cursor: pointer;
        flex-shrink: 0;
        z-index: 1;
        --icon-color: var(--border-strong, #9ca3af);
        transition:
          border-color 0.15s ease,
          color 0.15s ease;
      }

      .pager-dot:hover {
        border-color: var(--color-link-primary);
        --icon-color: var(--color-link-primary);
      }

      .pager-dot.loading {
        cursor: default;
        opacity: 0.5;
      }

      /* "More" label next to the pager dot - shares the event-row spacing
         and font size so the pager row sits on the same vertical rhythm */
      .pager-label {
        display: flex;
        align-items: center;
        padding: 0.4em 0.75em;
        margin: 0.1em 0;
        color: var(--border-strong, #9ca3af);
        cursor: pointer;
      }

      .pager-label:hover {
        color: var(--color-link-primary);
      }

      /* hovering either the dot or the label highlights both so they read
         as one interactive element - but the empty space of the row stays
         inert (no hover, no click) */
      .row.pager-row:has(.pager-dot:hover) .pager-label,
      .row.pager-row:has(.pager-label:hover) .pager-label {
        color: var(--color-link-primary);
      }

      .row.pager-row:has(.pager-label:hover) .pager-dot,
      .row.pager-row:has(.pager-dot:hover) .pager-dot {
        border-color: var(--color-link-primary);
        --icon-color: var(--color-link-primary);
      }

      .row.pager-row.loading .pager-dot,
      .row.pager-row.loading .pager-label,
      .row.pager-row.loading:has(.pager-dot:hover) .pager-dot,
      .row.pager-row.loading:has(.pager-dot:hover) .pager-label,
      .row.pager-row.loading:has(.pager-label:hover) .pager-dot,
      .row.pager-row.loading:has(.pager-label:hover) .pager-label {
        cursor: default;
        opacity: 0.5;
        color: var(--border-strong, #9ca3af);
        border-color: var(--border-strong, #9ca3af);
        --icon-color: var(--border-strong, #9ca3af);
      }

      /* the "now" divider - a rule running the full width */
      .row.now-row {
        position: relative;
      }

      .row.now-row::after {
        content: '';
        position: absolute;
        left: 0;
        right: 0;
        top: 50%;
        border-top: 1px solid var(--color-borders, rgba(0, 0, 0, 0.2));
        z-index: 0;
      }

      /* notice that campaign timelines are projections - sits below the
         timeline, bordered with the same dotted style as past campaign dots */
      .projection-note {
        max-width: 500px;
        margin: 0.5em 0.75em;
        padding: 0.5em 0.75em;
        border: 2px dotted var(--color-borders, rgba(0, 0, 0, 0.3));
        border-radius: var(--curvature);
        font-size: 0.8em;
        line-height: 1.45;
        color: var(--text-color);
        opacity: 0.7;
      }

      .now-label {
        z-index: 1;
        display: flex;
        align-items: center;
        margin: 1.5em 0;
        padding: 0 0.6em;
        background: var(--color-widget-bg, #fff);
        font-size: 0.75em;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-color);
        opacity: 0.5;
      }

      /* flat event entry - no card chrome. column layout stacks the title
         above any secondary metadata like the repeat schedule */
      .event {
        flex-grow: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 0.15em;
        padding: 0.4em 0.75em;
        margin: 0.1em 0;
        border-radius: var(--curvature);
      }

      .event.clickable {
        cursor: pointer;
      }

      .event.clickable:hover {
        background: var(--color-selection, rgba(0, 0, 0, 0.04));
      }

      .title {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 0.45em;
        color: var(--text-color);
        line-height: 1.4;
      }

      .title-text {
        flex: 1;
        min-width: 0;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
    `;
  }

  // the endpoint returns a custom {future, past, next_before} payload rather than
  // the paginated {results: [...]} shape that the store's fetch machinery expects,
  // so we fetch and assign data ourselves instead of relying on a monitored url
  private async loadEvents(): Promise<void> {
    if (!this.contact) {
      this.data = null;
      return;
    }

    // capture the contact at request time so a slower in-flight response for a
    // previous contact can't overwrite data for the contact we're now showing
    const requestedContact = this.contact;
    try {
      const response = await this.store.getUrl(
        `/contact/timeline/${encodeURIComponent(this.contact)}/`,
        { force: true }
      );
      if (this.contact !== requestedContact) {
        return;
      }
      this.data = response.json;
    } catch {
      // on failure leave the prior data in place so a transient blip doesn't
      // wipe the timeline; data is only cleared when the contact changes
      // (handled in updated()) or when there's no contact at all
    }
  }

  public refresh(): void {
    this.loadEvents();
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    if (changes.has('contact')) {
      // colors are assigned per-uuid in order of first appearance, so a switch
      // to a new contact must drop the previous assignments to avoid drift
      this.campaignColors = {};
      // blank the timeline immediately on a contact switch so the previous
      // contact's events aren't briefly visible while the new fetch is in flight
      this.data = null;
      // in-flight pager requests for the prior contact will bail on stale
      // contact, so reset the loading flags so the new contact's pagers aren't
      // blocked by the previous contact's still-resolving request
      this.loadingMore = false;
      this.loadingMoreFuture = false;
      this.loadEvents();
    }

    if (changes.has('data')) {
      // a fresh first page resets any paged-in events in both directions
      this.olderEvents = [];
      this.newerEvents = [];
      this.nextBefore = this.data ? (this.data.next_before ?? null) : null;
      this.nextAfter = this.data ? (this.data.next_after ?? null) : null;

      // eagerly assign campaign colors for everything in the first page so
      // render() can be a pure read of the map. Pager handlers extend the map
      // when later pages introduce campaigns not in the first page.
      if (this.data) {
        this.assignCampaignColors([
          ...(this.data.past || []),
          ...(this.data.future || [])
        ]);
      }

      // only notify consumers when we actually have data - skip the null state
      // between contact switch and first response (and any transient errors)
      // so listeners don't see a spurious count:0
      if (this.data !== null && this.data !== undefined) {
        // the badge reflects the total count of upcoming events, not just
        // what's currently visible on this page
        const count =
          typeof this.data.future_count === 'number'
            ? this.data.future_count
            : Array.isArray(this.data.future)
              ? this.data.future.length
              : 0;
        // empty mirrors the render()'s empty-state condition so a host
        // card can drop its chrome entirely when there's nothing to show
        const empty =
          count === 0 &&
          !(Array.isArray(this.data.campaigns) && this.data.campaigns.length) &&
          !(Array.isArray(this.data.future) && this.data.future.length) &&
          !(Array.isArray(this.data.past) && this.data.past.length);
        this.fireCustomEvent(CustomEventType.DetailsChanged, { count, empty });
      }
    }
  }

  // assign stable per-uuid colors for any campaigns seen in `events` that
  // aren't already in the map. Called from updated() on data change and from
  // pager handlers after a page is appended, so render() never mutates state.
  private assignCampaignColors(events: ScheduledEvent[]): void {
    for (const event of events) {
      if (event.type !== ScheduledEventType.CampaignEvent || !event.campaign) {
        continue;
      }
      const uuid = event.campaign.uuid;
      if (!this.campaignColors[uuid]) {
        const used = Object.keys(this.campaignColors).length;
        this.campaignColors[uuid] =
          CAMPAIGN_COLORS[used % CAMPAIGN_COLORS.length];
      }
    }
  }

  private getCampaignColor(uuid: string): string {
    return this.campaignColors[uuid] || CAMPAIGN_COLORS[0];
  }

  private getColor(event: ScheduledEvent): string {
    if (event.type === ScheduledEventType.ScheduledTrigger) {
      return TRIGGER_COLOR;
    }

    if (event.type !== ScheduledEventType.CampaignEvent || !event.campaign) {
      return BROADCAST_COLOR;
    }

    return this.getCampaignColor(event.campaign.uuid);
  }

  // broadcasts and triggers carry their type icon inside the dot;
  // campaign events use a plain dot since the campaign pill carries the context
  private getDotIcon(event: ScheduledEvent): string | null {
    if (event.type === ScheduledEventType.ScheduledTrigger) {
      return Icon.trigger;
    }
    if (event.type !== ScheduledEventType.CampaignEvent) {
      return Icon.broadcast;
    }
    return null;
  }

  public handleEventClicked(event: ScheduledEvent) {
    this.fireCustomEvent(CustomEventType.Selection, event);
  }

  // clicking a campaign or flow pill navigates to that entity's read page
  // instead of bubbling up to the row's event-read navigation
  public handlePillClicked(e: Event, ref: ObjectReference) {
    e.stopPropagation();
    this.fireCustomEvent(CustomEventType.Selection, ref);
  }

  // activate a non-button row on Enter/Space (matches native button behavior)
  // so keyboard users can reach clickable timeline rows and pager labels
  private handleActivationKey(e: KeyboardEvent, action: () => void) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      action();
    }
  }

  public async handleShowOlder() {
    if (this.loadingMore || !this.nextBefore) {
      return;
    }

    this.loadingMore = true;
    // capture the contact at request time so a paged response that returns
    // after the user has switched contacts can't append onto the new timeline
    const requestedContact = this.contact;
    const url = `/contact/timeline/${encodeURIComponent(
      this.contact
    )}/?before=${encodeURIComponent(this.nextBefore)}`;

    try {
      const response = await this.store.getUrl(url, { force: true });
      if (this.contact !== requestedContact) {
        return;
      }
      const page = response.json as EventsResponse;
      const newPast = page.past || [];
      this.assignCampaignColors(newPast);
      this.olderEvents = [...this.olderEvents, ...newPast];
      this.nextBefore = page.next_before ?? null;
    } catch {
      if (this.contact !== requestedContact) {
        return;
      }
      // on failure leave the accumulated events in place but stop offering
      // the same failing page - clearing the cursor hides the pager
      this.nextBefore = null;
    } finally {
      // only clear the flag if we're still on the original contact - the
      // contact-change handler in updated() already cleared it, and clearing
      // again here would unblock the new contact's in-flight pager request
      // and allow a duplicate fetch of the same cursor
      if (this.contact === requestedContact) {
        this.loadingMore = false;
      }
    }
  }

  public async handleShowMore() {
    if (this.loadingMoreFuture || !this.nextAfter) {
      return;
    }

    this.loadingMoreFuture = true;
    const requestedContact = this.contact;
    const url = `/contact/timeline/${encodeURIComponent(
      this.contact
    )}/?after=${encodeURIComponent(this.nextAfter)}`;

    try {
      const response = await this.store.getUrl(url, { force: true });
      if (this.contact !== requestedContact) {
        return;
      }
      const page = response.json as EventsResponse;
      const newFuture = page.future || [];
      this.assignCampaignColors(newFuture);
      this.newerEvents = [...this.newerEvents, ...newFuture];
      this.nextAfter = page.next_after ?? null;
    } catch {
      if (this.contact !== requestedContact) {
        return;
      }
      this.nextAfter = null;
    } finally {
      if (this.contact === requestedContact) {
        this.loadingMoreFuture = false;
      }
    }
  }

  private renderTime(event: ScheduledEvent): TemplateResult {
    // anchor durations to the server's "now" so they stay tolerant of clock
    // skew and don't silently drift when the page is left open
    return html`
      <temba-tip text=${this.store.formatDate(event.scheduled)} position="top">
        ${this.store.getShortDurationFromIso(event.scheduled, this.data?.now)}
      </temba-tip>
    `;
  }

  private renderEvent(event: ScheduledEvent): TemplateResult {
    const clickable = event.type !== ScheduledEventType.SentBroadcast;
    const isMessage = !!event.message;

    // message events display the message text; flow-bearing events show a
    // clickable flow pill linking to the flow (the "start" action is implied)
    const body = isMessage
      ? html`<div class="title-text">
          <temba-expression-highlight
            >${event.message}</temba-expression-highlight
          >
        </div>`
      : event.flow
        ? html`<temba-label
            type="flow"
            clickable
            @click=${(e: Event) => this.handlePillClicked(e, event.flow)}
            >${event.flow.name}</temba-label
          >`
        : html``;

    return html`
      <div
        class="event ${clickable ? 'clickable' : ''}"
        role=${clickable ? 'button' : 'presentation'}
        tabindex=${clickable ? '0' : '-1'}
        @click=${clickable ? () => this.handleEventClicked(event) : null}
        @keydown=${clickable
          ? (e: KeyboardEvent) =>
              this.handleActivationKey(e, () => this.handleEventClicked(event))
          : null}
      >
        <div class="title">${body}</div>
      </div>
    `;
  }

  private renderRow(
    time: TemplateResult,
    dot: TemplateResult,
    content: TemplateResult,
    first: boolean,
    last: boolean
  ): TemplateResult {
    return html`
      <div class="row">
        <div class="time">${time}</div>
        <div class="track">
          <div class="line ${first ? 'hidden' : ''}"></div>
          ${dot}
          <div class="line ${last ? 'hidden' : ''}"></div>
        </div>
        ${content}
      </div>
    `;
  }

  private renderCampaigns(campaigns: ObjectReference[]): TemplateResult | null {
    if (campaigns.length === 0) {
      return null;
    }
    return html`
      <div class="campaigns">
        <div class="campaigns-label">${this.lang_campaigns_label}</div>
        ${campaigns.map(
          (campaign) =>
            html`<div
              class="campaign-pill"
              style="--pill-hue:${this.getCampaignColor(campaign.uuid)}"
              role="button"
              tabindex="0"
              @click=${(e: Event) => this.handlePillClicked(e, campaign)}
              @keydown=${(e: KeyboardEvent) =>
                this.handleActivationKey(e, () =>
                  this.handlePillClicked(e, campaign)
                )}
            >
              <span class="campaign-dot"></span>${campaign.name}
            </div>`
        )}
      </div>
    `;
  }

  public render(): TemplateResult {
    if (!this.data) {
      return html``;
    }

    // tolerate a malformed/empty response rather than throwing
    const campaigns = Array.isArray(this.data.campaigns)
      ? this.data.campaigns
      : [];
    const future = [
      ...(Array.isArray(this.data.future) ? this.data.future : []),
      ...this.newerEvents
    ];
    const pastDescending = [
      ...(Array.isArray(this.data.past) ? this.data.past : []),
      ...this.olderEvents
    ];

    if (
      campaigns.length === 0 &&
      future.length === 0 &&
      pastDescending.length === 0
    ) {
      return html`<div class="empty">
        <slot name="empty">
          <div class="empty-extras">
            <temba-icon name=${Icon.schedule} size="2"></temba-icon>
          </div>
          <div class="empty-title">${this.lang_empty}</div>
          <div class="empty-extras">
            <div class="empty-help">${this.lang_empty_help}</div>
            <a class="empty-link" href="/campaign/" onclick="goto(event, this)"
              >${this.lang_campaigns_link}</a
            >
          </div>
        </slot>
      </div>`;
    }

    // the timeline reads oldest to newest, top to bottom: an "older" pager,
    // then past events, the "now" divider, upcoming events, and a "show more"
    // pager at the bottom
    type Row = {
      kind: 'event' | 'now' | 'more-past' | 'more-future';
      event?: ScheduledEvent;
      past?: boolean;
    };
    const rows: Row[] = [];

    if (this.nextBefore) {
      rows.push({ kind: 'more-past' });
    }
    [...pastDescending]
      .reverse()
      .forEach((event) => rows.push({ kind: 'event', event, past: true }));
    rows.push({ kind: 'now' });
    future.forEach((event) => rows.push({ kind: 'event', event, past: false }));
    if (this.nextAfter) {
      rows.push({ kind: 'more-future' });
    }

    return html`
      ${this.renderCampaigns(campaigns)}
      <div class="timeline">
        ${rows.map((row, idx) => {
          const first = idx === 0;
          const last = idx === rows.length - 1;

          if (row.kind === 'now') {
            return html`
              <div class="row now-row">
                <div class="time"></div>
                <div class="track">
                  <div class="line ${first ? 'hidden' : ''}"></div>
                  <div class="dot now"></div>
                  <div class="line ${last ? 'hidden' : ''}"></div>
                </div>
                <div class="now-label">${this.lang_now}</div>
              </div>
            `;
          }

          if (row.kind === 'more-past') {
            return html`
              <div class="row pager-row ${this.loadingMore ? 'loading' : ''}">
                <div class="time"></div>
                <div class="track">
                  <div class="line ${first ? 'hidden' : ''}"></div>
                  <button
                    class="pager-dot ${this.loadingMore ? 'loading' : ''}"
                    @click=${this.handleShowOlder}
                    aria-label=${this.lang_show_older}
                    title=${this.lang_show_older}
                  >
                    <temba-icon name=${Icon.up_double} size="1"></temba-icon>
                  </button>
                  <div class="line ${last ? 'hidden' : ''}"></div>
                </div>
                <div
                  class="pager-label"
                  role="button"
                  tabindex="0"
                  aria-label=${this.lang_show_older}
                  @click=${this.handleShowOlder}
                  @keydown=${(e: KeyboardEvent) =>
                    this.handleActivationKey(e, () => this.handleShowOlder())}
                  title=${this.lang_show_older}
                >
                  ${this.lang_more}
                </div>
              </div>
            `;
          }

          if (row.kind === 'more-future') {
            return html`
              <div
                class="row pager-row ${this.loadingMoreFuture ? 'loading' : ''}"
              >
                <div class="time"></div>
                <div class="track">
                  <div class="line ${first ? 'hidden' : ''}"></div>
                  <button
                    class="pager-dot ${this.loadingMoreFuture ? 'loading' : ''}"
                    @click=${this.handleShowMore}
                    aria-label=${this.lang_show_more}
                    title=${this.lang_show_more}
                  >
                    <temba-icon name=${Icon.down_double} size="1"></temba-icon>
                  </button>
                  <div class="line ${last ? 'hidden' : ''}"></div>
                </div>
                <div
                  class="pager-label"
                  role="button"
                  tabindex="0"
                  aria-label=${this.lang_show_more}
                  @click=${this.handleShowMore}
                  @keydown=${(e: KeyboardEvent) =>
                    this.handleActivationKey(e, () => this.handleShowMore())}
                  title=${this.lang_show_more}
                >
                  ${this.lang_more}
                </div>
              </div>
            `;
          }

          const dotIcon = this.getDotIcon(row.event);
          return this.renderRow(
            this.renderTime(row.event),
            html`<div
              class="dot ${row.past ? 'past' : 'future'}"
              style="--dot-color:${this.getColor(row.event)}"
            >
              ${dotIcon
                ? html`<temba-icon name=${dotIcon} size="0.65"></temba-icon>`
                : null}
            </div>`,
            this.renderEvent(row.event),
            first,
            last
          );
        })}
      </div>
      ${future.length > 0
        ? html`<div class="projection-note">${this.lang_projected_info}</div>`
        : null}
    `;
  }
}
