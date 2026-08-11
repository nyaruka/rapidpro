import { html, TemplateResult } from 'lit-html';
import { css, PropertyValues } from 'lit';
import { property, state } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { getStore } from '../store/Store';
import { FlowDefinition } from '../store/flow-definition';
import { fetchResults } from '../utils';
import { FLOW_SPEC_VERSION } from '../store/AppState';
import {
  labelsFor,
  normalizeChanges,
  RevisionChanges,
  summarizeChanges
} from './revision-summary';

const GROUP_WINDOW_MS = 15 * 60 * 1000;
const MAX_GROUP_LABELS = 3;

export interface Revision {
  id: number;
  user: {
    id?: number;
    email?: string;
    username?: string;
    first_name?: string;
    last_name?: string;
    name?: string;
  };
  created_on: string;
  comment?: string;
  changes?: RevisionChanges | null;
}

export class RevisionsWindow extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: contents;
      }
    `;
  }

  @property({ type: String })
  flow = '';

  @property({ type: Boolean })
  hidden = true;

  @property({ type: Boolean })
  saving = false;

  @state()
  private revisions: Revision[] = [];

  @state()
  private viewingRevision: Revision | null = null;

  @state()
  private isLoading = false;

  private preRevertState: {
    definition: FlowDefinition;
    dirtyDate: Date | null;
  } | null = null;
  private browseLanguageCode: string | null = null;
  private fetchRequestId = 0;

  public get isViewingRevision(): boolean {
    return this.viewingRevision !== null;
  }

  public refresh(): void {
    if (!this.hidden) {
      this.fetchRevisions();
    }
  }

  protected updated(changes: PropertyValues): void {
    super.updated(changes);
    if (
      changes.has('hidden') &&
      !this.hidden &&
      changes.get('hidden') === true
    ) {
      this.fetchRevisions();
    }
  }

  public close(): void {
    this.resetScroll();
    if (this.viewingRevision) {
      this.cancelRevisionView();
    }
    this.fireCustomEvent(CustomEventType.RevisionsClosed);
  }

  public render(): TemplateResult {
    return html`
      <temba-floating-window
        id="revisions-window"
        name="revisions"
        header="Revisions"
        icon="revisions"
        .width=${340}
        .maxHeight=${500}
        .top=${120}
        color="rgb(142, 94, 167)"
        .saving=${this.saving}
        .hidden=${this.hidden}
        @temba-dialog-hidden=${() => this.close()}
      >
        <div class="localization-window-content">
          <div
            class="revisions-list"
            style="display:flex; flex-direction:column; gap:8px; overflow-y:auto; padding-bottom:10px;"
          >
            ${this.isLoading && !this.revisions.length
              ? html`<temba-loading></temba-loading>`
              : this.revisions.map((rev, index) => {
                  const isCurrent = index === 0;
                  const isSelected = this.viewingRevision?.id === rev.id;
                  const summary = summarizeChanges(rev.changes);
                  return html`
                    <div
                      class="revision-item ${isSelected
                        ? 'selected'
                        : ''} ${isCurrent ? 'current' : ''}"
                      style="padding:8px; border-radius:4px; cursor:pointer; background:${isSelected
                        ? '#f0f6ff'
                        : '#f9fafb'}; border:1px solid ${isSelected
                        ? '#a4cafe'
                        : '#e5e7eb'}; transition: all 0.2s ease;"
                      @click=${() => this.handleRevisionClick(rev)}
                    >
                      ${summary
                        ? html`<div
                            class="revision-summary"
                            style="font-size:13px; color:#111827; line-height:1.3;"
                          >
                            ${summary}
                          </div>`
                        : ''}
                      <div
                        class="revision-meta"
                        style="display:flex; justify-content:space-between; align-items:center; gap:8px; min-height:20px; font-size:11px; color:#6b7280; margin-top:${summary
                          ? '2px'
                          : '0'};"
                      >
                        <div style="flex:1; min-width:0;">
                          <temba-date
                            value=${rev.created_on}
                            display="duration"
                          ></temba-date>
                          · ${this.renderUser(rev.user)}
                        </div>
                        ${isCurrent
                          ? html`<div
                              class="current-label"
                              style="font-size:10px; font-weight:600; text-transform:uppercase; color:#6b7280; background:#e5e7eb; padding:2px 6px; border-radius:10px; letter-spacing:0.5px; flex-shrink:0;"
                            >
                              Current
                            </div>`
                          : isSelected
                            ? html`<button
                                class="revert-button"
                                style="font-size:10px; font-weight:600; text-transform:uppercase; color:#1e3a8a; background:#a4cafe; padding:2px 6px; border-radius:10px; letter-spacing:0.5px; border:none; cursor:pointer; flex-shrink:0;"
                                @click=${(e: Event) => {
                                  e.stopPropagation();
                                  this.handleRevertClick();
                                }}
                              >
                                Revert
                              </button>`
                            : html``}
                      </div>

                      ${rev.comment
                        ? html`<div
                            style="font-size:12px; color:#4b5563; margin-top:4px;"
                          >
                            ${rev.comment}
                          </div>`
                        : ''}
                    </div>
                  `;
                })}
          </div>
        </div>
      </temba-floating-window>
    `;
  }

  // --- Private ---

  private renderUser(user: Revision['user']): TemplateResult | string {
    if (user?.email === 'system') {
      return html`<em>System update</em>`;
    }
    return user?.name || user?.username || '';
  }

  private async fetchRevisions() {
    const requestId = ++this.fetchRequestId;
    this.isLoading = true;
    try {
      const results = await fetchResults(
        `/flow/revisions/${this.flow}/?version=${FLOW_SPEC_VERSION}`
      );
      if (requestId !== this.fetchRequestId) return;
      this.revisions = this.collapseRevisions(results);
    } catch (e) {
      if (requestId !== this.fetchRequestId) return;
      console.error('Error fetching revisions', e);
    } finally {
      if (requestId === this.fetchRequestId) {
        this.isLoading = false;
      }
    }
  }

  // Lump revisions made in a continuous editing session (within 15 minutes
  // of each other, by the same author) onto their most recent member,
  // merging the tag sets so the summary covers everything that happened in
  // the window. The merged revision is capped at three distinct displayed
  // labels — once a fourth would be introduced we break out into a new row.
  private collapseRevisions(revisions: Revision[]): Revision[] {
    // Normalize at the boundary so the rest of the logic reasons about real
    // edits only. After this step, `changes === null` is the single signal
    // for "no-op" — used both for the author-barrier bypass and for keeping
    // housekeeping tags out of the merged tag set and label cap.
    const cleaned = revisions.map((r) => ({
      ...r,
      changes: normalizeChanges(r.changes)
    }));
    // The API returns newest-first today; sort defensively so the head/window
    // logic stays correct if that ever changes.
    const sorted = [...cleaned].sort(
      (a, b) =>
        new Date(b.created_on).getTime() - new Date(a.created_on).getTime()
    );
    const result: Revision[] = [];
    let group: Revision[] = [];
    let groupLabels = new Set<string>();
    let groupHasRealChange = false;

    const flush = () => {
      if (group.length === 0) return;
      const head = group[0];
      // Pick the user from the most recent real-change revision in the
      // group. No-op authors (typically the system, doing spec bumps)
      // shouldn't appear as the editor when a real user's edit was
      // absorbed into the row — that would mislabel the change as
      // "System update" even though a real person did the work. Fall back
      // to the head if every revision was a no-op.
      const realChange = group.find((r) => r.changes);
      const displayUser = realChange?.user ?? head.user;
      const tagSet = new Set<string>();
      let anyKnown = false;
      for (const r of group) {
        if (r.changes) {
          anyKnown = true;
          for (const tag of r.changes.tags || []) tagSet.add(tag);
        }
      }
      result.push({
        ...head,
        user: displayUser,
        changes: anyKnown ? { tags: Array.from(tagSet) } : null
      });
      group = [];
      groupLabels = new Set();
      groupHasRealChange = false;
    };

    for (const rev of sorted) {
      if (group.length === 0) {
        group.push(rev);
        groupLabels = labelsFor(rev.changes);
        groupHasRealChange = !!rev.changes;
        continue;
      }
      const head = group[0];
      const headTime = new Date(head.created_on).getTime();
      const revTime = new Date(rev.created_on).getTime();
      // Compare on whichever identifier the server provides — real data
      // arrives with `email`, while test fixtures use `username`. Falling
      // back through the chain keeps both shapes working.
      const headId = head.user?.email ?? head.user?.username;
      const revId = rev.user?.email ?? rev.user?.username;
      // Two conditions bypass the time/author barriers:
      //   1. The incoming rev is itself a no-op — it carries no editorial
      //      intent and should disappear into whichever group it neighbors.
      //   2. The group hasn't accumulated a real change yet — we never want
      //      to surface a row showing "nothing changed", so a no-op-only
      //      chain reaches forward to absorb the first real edit even if
      //      that edit is far away in time or by a different author.
      const isNoOp = !rev.changes;
      const bypassBarriers = isNoOp || !groupHasRealChange;
      const withinWindow =
        bypassBarriers || headTime - revTime < GROUP_WINDOW_MS;
      const sameAuthor = bypassBarriers || headId === revId;
      const prospective = new Set([...groupLabels, ...labelsFor(rev.changes)]);
      // The label cap is meaningful only when adding a real change to a
      // group that already has one. A no-op contributes zero labels by
      // construction, so it never trips the cap; and a no-op-only chain
      // reaching forward to absorb its first real edit must ignore the cap
      // too, or a sweeping edit (4+ label areas) would still strand the
      // no-op group as an empty-summary row.
      const fitsLabelCap =
        isNoOp || !groupHasRealChange || prospective.size <= MAX_GROUP_LABELS;

      if (withinWindow && sameAuthor && fitsLabelCap) {
        group.push(rev);
        groupLabels = prospective;
        if (!isNoOp) groupHasRealChange = true;
      } else {
        flush();
        group.push(rev);
        groupLabels = labelsFor(rev.changes);
        groupHasRealChange = !!rev.changes;
      }
    }
    flush();
    return result;
  }

  private async handleRevisionClick(revision: Revision) {
    if (this.viewingRevision?.id === revision.id) {
      return;
    }

    const store = getStore().getState();

    if (!this.viewingRevision) {
      this.preRevertState = {
        definition: store.flowDefinition,
        dirtyDate: store.dirtyDate
      };
      this.browseLanguageCode = store.languageCode;
    }

    this.viewingRevision = revision;
    this.isLoading = true;

    this.fireCustomEvent(CustomEventType.RevisionViewed, { revision });

    try {
      await store.fetchRevision(
        `/flow/revisions/${this.flow}`,
        revision.id.toString()
      );
      if (this.browseLanguageCode) {
        store.setLanguageCode(this.browseLanguageCode);
      }
    } catch (e) {
      console.error('Error fetching revision details', e);
      this.cancelRevisionView();
    } finally {
      this.isLoading = false;
    }
  }

  private cancelRevisionView() {
    const store = getStore().getState();
    const preservedLanguageCode = this.browseLanguageCode || store.languageCode;

    if (this.preRevertState) {
      const currentInfo = store.flowInfo;
      store.setFlowContents({
        definition: this.preRevertState.definition,
        info: currentInfo
      });
      if (this.preRevertState.dirtyDate) {
        store.setDirtyDate(this.preRevertState.dirtyDate);
      }
      if (preservedLanguageCode) {
        store.setLanguageCode(preservedLanguageCode);
      }
    } else {
      store.fetchRevision(`/flow/revisions/${this.flow}`).finally(() => {
        if (preservedLanguageCode) {
          store.setLanguageCode(preservedLanguageCode);
        }
      });
    }

    this.viewingRevision = null;
    this.preRevertState = null;
    this.browseLanguageCode = null;
    this.fireCustomEvent(CustomEventType.RevisionCancelled);
  }

  private async handleRevertClick() {
    if (!this.viewingRevision || !this.preRevertState) return;

    const store = getStore().getState();
    const preservedLanguageCode = this.browseLanguageCode || store.languageCode;

    const definitionToSave = {
      ...store.flowDefinition,
      revision: this.preRevertState.definition.revision
    };

    this.viewingRevision = null;
    this.preRevertState = null;
    this.browseLanguageCode = null;

    this.fireCustomEvent(CustomEventType.RevisionReverted, {
      definition: definitionToSave,
      languageCode: preservedLanguageCode
    });
  }

  private resetScroll() {
    const win = this.shadowRoot?.querySelector('temba-floating-window');
    const list = win?.shadowRoot?.querySelector('.body');
    if (list) {
      list.scrollTop = 0;
    }
  }
}
