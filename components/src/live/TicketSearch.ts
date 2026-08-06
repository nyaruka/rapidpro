import { css, html, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { ModalSearchResult, SearchModal } from '../layout/SearchModal';
import { getUrl } from '../utils';

// The matched message event as the endpoint returns it
export interface TicketSearchEvent {
  uuid: string;
  type: string;
  created_on: string;
  ticket_uuid?: string;
  msg?: { text?: string };
  [key: string]: any;
}

export interface TicketSearchResult extends ModalSearchResult {
  contact: { uuid: string; name: string };
  ticket: { uuid: string; status: string };
  event: TicketSearchEvent;
  // The query that produced this result, so selection handlers can re-run
  // the search within the ticket
  query: string;
}

const BADGE_COLOR = '#6b7280';

// rough number of characters that fit on a result row - the snippet is
// windowed around the match so the match stays visible if CSS clips the tail
const SNIPPET_BUDGET = 60;

// the shortest prefix we'll fall back to when a query term doesn't appear
// literally - short enough to cover most inflections, long enough that the
// highlight still points at the word the user searched for
const MIN_PREFIX = 4;

// strips everything but letters and numbers, so punctuation in the query
// doesn't keep a term from matching the message text
const stripNonWord = (text: string) => text.replace(/[^\p{L}\p{N}]/gu, '');

// same, but only at the ends, so the words of a multi-word query stay apart
const stripOuterNonWord = (text: string) =>
  text.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');

// the candidates to look for, in priority order, without duplicates
const withoutDupes = (candidates: string[]) =>
  candidates.filter(
    (candidate, index) => !!candidate && candidates.indexOf(candidate) === index
  );

/**
 * Searches message text across all of an org's ticket chats. Searching hits
 * an endpoint, so it waits for Enter rather than running on every keystroke.
 */
export class TicketSearch extends SearchModal<TicketSearchResult> {
  static styles = [
    SearchModal.styles,
    css`
      .result-type-badge {
        max-width: 35%;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .result-text {
        flex-grow: 1;
      }

      .result-date {
        flex-shrink: 0;
        font-size: 11px;
        color: #9ca3af;
      }
    `
  ];

  @property({ type: String })
  endpoint = '/ticket/search/';

  // searching hits an endpoint, so wait for Enter
  searchOnEnter = true;

  // how many matches the last search found in tickets this user can't access,
  // so an empty result set can say why it's empty
  @state()
  private dropped = 0;

  // the in-flight request, aborted when it's superseded or the modal closes
  private abortController: AbortController = null;

  protected cancelSearch(): void {
    this.abortSearch();
    this.dropped = 0;
  }

  private abortSearch(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  protected getSearchLabel(): string {
    return 'Search tickets';
  }

  protected renderHint(): TemplateResult {
    return html`<div class="hint">
      <kbd>Enter</kbd> to search &nbsp; <kbd>Esc</kbd> to close
    </div>`;
  }

  /**
   * The endpoint filters matches down to the tickets this user can access
   * after the search itself is capped, so a query that matched plenty can
   * still come back empty. Say so rather than claiming nothing matched.
   */
  protected getNoResultsMessage(): string {
    return this.dropped > 0
      ? 'No matches in tickets you can access'
      : super.getNoResultsMessage();
  }

  protected async performSearch(query: string): Promise<TicketSearchResult[]> {
    this.abortSearch();
    this.dropped = 0;

    const controller = new AbortController();
    this.abortController = controller;

    const joiner = this.endpoint.includes('?') ? '&' : '?';
    const response = await getUrl(
      `${this.endpoint}${joiner}text=${encodeURIComponent(query)}`,
      controller
    );

    if (this.abortController === controller) {
      this.abortController = null;
    }

    const json = response.json as any;
    this.dropped = json.dropped || 0;

    const results = json.results || [];
    return results.map((result: any) => this.toSearchResult(result, query));
  }

  /**
   * Locates a term in the message text, falling back to progressively
   * shorter prefixes of it. The backend matches on analyzed text, so a query
   * term ("helping") can match a message that only contains a stemmed or
   * inflected form of it ("helped") - highlighting the longest prefix that
   * does appear keeps the match visible rather than showing nothing.
   */
  private findTerm(
    lowerText: string,
    term: string,
    minLength: number
  ): { start: number; length: number } | null {
    for (let length = term.length; length >= minLength; length--) {
      const idx = lowerText.indexOf(term.slice(0, length));
      if (idx !== -1) {
        return { start: idx, length };
      }
    }
    return null;
  }

  private toSearchResult(result: any, query: string): TicketSearchResult {
    const text = result.event?.msg?.text || result.event?.text || '';
    const lowerText = text.toLowerCase();
    const lowerQuery = query.trim().toLowerCase();

    let matchStart = -1;
    let matchLength = 0;

    // highlight the whole query if it appears verbatim (with or without any
    // punctuation it's wrapped in), otherwise the first matching term - the
    // backend matches terms independently, and against analyzed text, so a
    // term is tried both as typed and stripped of its punctuation
    const queries = withoutDupes([lowerQuery, stripOuterNonWord(lowerQuery)]);
    for (const candidate of queries) {
      const idx = lowerText.indexOf(candidate);
      if (idx !== -1) {
        matchStart = idx;
        matchLength = candidate.length;
        break;
      }
    }

    const terms = withoutDupes(
      lowerQuery.split(/\s+/).reduce((all: string[], term) => {
        all.push(term, stripNonWord(term));
        return all;
      }, [])
    );

    // literal matches first, so an exact hit on a later term beats a
    // prefix hit on an earlier one
    for (const minLength of [Infinity, MIN_PREFIX]) {
      if (matchStart !== -1) {
        break;
      }
      for (const term of terms) {
        const match = this.findTerm(
          lowerText,
          term,
          Math.min(minLength, term.length)
        );
        if (match) {
          matchStart = match.start;
          matchLength = match.length;
          break;
        }
      }
    }

    if (matchStart === -1) {
      matchStart = 0;
      matchLength = 0;
    }

    return {
      typeName: result.contact?.name || 'Unknown',
      color: BADGE_COLOR,
      fullText: text,
      matchStart,
      matchLength,
      contact: result.contact,
      ticket: result.ticket,
      event: result.event,
      query: query.trim()
    };
  }

  /**
   * Unlike the base (which anchors the match near the start and lets CSS
   * clip the tail), message snippets are windowed to roughly center the
   * match, with ellipses marking clipped context on either side.
   */
  protected renderMatchText(result: TicketSearchResult): TemplateResult {
    const text = result.fullText.replace(/\n/g, ' ');
    const { matchStart, matchLength } = result;

    if (matchLength === 0) {
      return html`${text}`;
    }

    const matchEnd = matchStart + matchLength;
    const highlight = (start: number, end: number) =>
      html`${start > 0 ? '…' : ''}${text.slice(
        start,
        matchStart
      )}<mark>${text.slice(matchStart, matchEnd)}</mark>${text.slice(
        matchEnd,
        end
      )}${end < text.length ? '…' : ''}`;

    if (text.length <= SNIPPET_BUDGET) {
      return highlight(0, text.length);
    }

    // center the match in the character budget, shifting the window back
    // into range when the match sits near either end of the text
    const context = Math.max(0, SNIPPET_BUDGET - matchLength);
    let start = matchStart - Math.floor(context / 2);
    let end = matchEnd + Math.ceil(context / 2);
    if (start < 0) {
      end = Math.min(text.length, end - start);
      start = 0;
    }
    if (end > text.length) {
      start = Math.max(0, start - (end - text.length));
      end = text.length;
    }

    return highlight(start, end);
  }

  protected renderResultContent(result: TicketSearchResult): TemplateResult {
    return html`
      ${super.renderResultContent(result)}
      <div class="result-date">
        <temba-date
          value=${result.event?.created_on}
          display="duration"
        ></temba-date>
      </div>
    `;
  }
}
