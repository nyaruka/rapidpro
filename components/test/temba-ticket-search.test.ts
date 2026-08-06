import { fixture, expect, waitUntil, oneEvent } from '@open-wc/testing';
import { TicketSearch, TicketSearchResult } from '../src/live/TicketSearch';
import { clearMockGets, mockGET } from './utils.test';

if (!customElements.get('temba-ticket-search')) {
  customElements.define('temba-ticket-search', TicketSearch);
}

const LONG_TEXT =
  'Hello there, I was wondering if you could possibly help me figure out ' +
  'why my order from last week still has not arrived at my house yet';

const RESPONSE = {
  results: [
    {
      contact: { uuid: 'contact-1', name: 'Ben Haggerty' },
      ticket: { uuid: 'ticket-1', status: 'open' },
      event: {
        uuid: 'event-1',
        type: 'msg_received',
        msg: { text: 'I need help with my order' },
        created_on: '2025-03-01T13:00:00Z',
        ticket_uuid: 'ticket-1'
      }
    },
    {
      contact: { uuid: 'contact-2', name: 'Joe' },
      ticket: { uuid: 'ticket-2', status: 'closed' },
      event: {
        uuid: 'event-2',
        type: 'msg_created',
        msg: { text: 'Can you help me reset my password?' },
        created_on: '2025-03-02T13:00:00Z',
        ticket_uuid: 'ticket-2'
      }
    },
    {
      contact: { uuid: 'contact-3', name: 'Norbert' },
      ticket: { uuid: 'ticket-3', status: 'open' },
      event: {
        uuid: 'event-3',
        type: 'msg_received',
        msg: { text: LONG_TEXT },
        created_on: '2025-03-03T13:00:00Z',
        ticket_uuid: 'ticket-3'
      }
    }
  ]
};

// the backend matches analyzed text, so a query can come back with messages
// that only contain an inflected form of the term
const STEMMED_RESPONSE = {
  results: [
    {
      contact: { uuid: 'contact-1', name: 'Ben Haggerty' },
      ticket: { uuid: 'ticket-1', status: 'open' },
      event: {
        uuid: 'event-1',
        type: 'msg_received',
        msg: { text: 'She helped me with my order' },
        created_on: '2025-03-01T13:00:00Z',
        ticket_uuid: 'ticket-1'
      }
    }
  ]
};

const createSearch = async (): Promise<TicketSearch> => {
  const el = (await fixture(
    '<temba-ticket-search></temba-ticket-search>'
  )) as TicketSearch;
  el.show();
  await el.updateComplete;
  return el;
};

const setQuery = async (el: TicketSearch, query: string): Promise<void> => {
  const input = el.shadowRoot.querySelector('input') as HTMLInputElement;
  input.value = query;
  input.dispatchEvent(new InputEvent('input', { bubbles: true }));
  await el.updateComplete;
};

const pressKey = async (el: TicketSearch, key: string): Promise<void> => {
  const input = el.shadowRoot.querySelector('input') as HTMLInputElement;
  input.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  await el.updateComplete;
};

const getResults = (el: TicketSearch): TicketSearchResult[] => {
  return (el as any).results as TicketSearchResult[];
};

describe('temba-ticket-search', () => {
  beforeEach(() => {
    // tests that re-mock the endpoint leave their own mocks behind, and the
    // first registered match wins, so start each test from a clean slate
    clearMockGets();

    // registered first so they win over the catch-all below
    mockGET(/\/ticket\/search\/\?text=helping/, STEMMED_RESPONSE);
    mockGET(/\/ticket\/search\/\?text=kaboom/, { error: 'boom' }, {}, '500');
    mockGET(/\/ticket\/search\/\?text=.*/, RESPONSE);
  });

  it('does not search as the user types', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');

    expect(getResults(el).length).to.equal(0);
    const hint = el.shadowRoot.querySelector('.hint');
    expect(hint.textContent).to.contain('to search');
  });

  it('searches when the user hits enter', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);

    const results = getResults(el);
    expect(results.length).to.equal(3);
    expect(results[0].typeName).to.equal('Ben Haggerty');
    expect(results[0].ticket.uuid).to.equal('ticket-1');
    expect(results[0].event.uuid).to.equal('event-1');
    expect(results[0].fullText).to.equal('I need help with my order');
    expect(results[0].matchStart).to.equal('I need '.length);
    expect(results[0].matchLength).to.equal('help'.length);

    await el.updateComplete;
    expect(el.shadowRoot.querySelectorAll('.result-item').length).to.equal(3);
    expect(el.shadowRoot.querySelector('.result-count').textContent).to.contain(
      '3 results'
    );
  });

  it('shows the full message when it fits, with the match highlighted', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);
    await el.updateComplete;

    const resultText = el.shadowRoot
      .querySelectorAll('.result-item')[0]
      .querySelector('.result-text');
    expect(resultText.textContent).to.equal('I need help with my order');
    expect(resultText.querySelector('mark').textContent).to.equal('help');
  });

  it('centers the match in the snippet for long messages', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);
    await el.updateComplete;

    const resultText = el.shadowRoot
      .querySelectorAll('.result-item')[2]
      .querySelector('.result-text');
    const mark = resultText.querySelector('mark');
    expect(mark.textContent).to.equal('help');

    // clipped on both sides with the match roughly centered
    const full = resultText.textContent;
    expect(full.startsWith('…')).to.equal(true);
    expect(full.endsWith('…')).to.equal(true);
    const before = full.indexOf(mark.textContent);
    const after = full.length - before - mark.textContent.length;
    expect(Math.abs(before - after)).to.be.at.most(2);
  });

  it('highlights the first matching term for multi-word queries', async () => {
    const el = await createSearch();
    await setQuery(el, 'password help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);

    // "password help" doesn't appear verbatim so we highlight the first
    // term that does
    const result = getResults(el)[1];
    expect(result.fullText).to.equal('Can you help me reset my password?');
    expect(result.matchStart).to.equal(result.fullText.indexOf('password'));
    expect(result.matchLength).to.equal('password'.length);
  });

  it('selects the highlighted result on enter after searching', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);
    await el.updateComplete;

    // move the highlight down and select
    await pressKey(el, 'ArrowDown');
    const listener = oneEvent(el, 'temba-search-result-selected', false);
    await pressKey(el, 'Enter');
    const event = await listener;

    expect(event.detail.ticket.uuid).to.equal('ticket-2');
    expect(event.detail.contact.uuid).to.equal('contact-2');
    expect(el.open).to.equal(false);
  });

  it('highlights the longest matching prefix of an inflected term', async () => {
    const el = await createSearch();
    await setQuery(el, 'helping?');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);
    await el.updateComplete;

    // "helping?" appears nowhere literally, so back off to the longest
    // prefix that does - punctuation and all - rather than showing no
    // highlight at all
    const result = getResults(el)[0];
    expect(result.fullText).to.equal('She helped me with my order');
    expect(result.matchStart).to.equal('She '.length);
    expect(result.matchLength).to.equal('help'.length);

    const mark = el.shadowRoot
      .querySelector('.result-item')
      .querySelector('mark');
    expect(mark.textContent).to.equal('help');
  });

  it('shows a failure message when the search request fails', async () => {
    const el = await createSearch();
    await setQuery(el, 'kaboom');
    await pressKey(el, 'Enter');

    await waitUntil(() => !!el.shadowRoot.querySelector('.no-results'));
    expect(el.shadowRoot.querySelector('.no-results').textContent).to.contain(
      'Search failed'
    );

    // the failed query is still pending, so Enter runs it again
    clearMockGets();
    mockGET(/\/ticket\/search\/\?text=.*/, RESPONSE);
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);
    expect(el.shadowRoot.querySelector('.no-results')).to.equal(null);
  });

  it('reports an empty result set as no matches', async () => {
    clearMockGets();
    mockGET(/\/ticket\/search\/\?text=.*/, { results: [], dropped: 0 });

    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');

    await waitUntil(() => !!el.shadowRoot.querySelector('.no-results'));
    expect(el.shadowRoot.querySelector('.no-results').textContent).to.contain(
      'No matches found'
    );
  });

  it('says so when the only matches were in inaccessible tickets', async () => {
    clearMockGets();
    mockGET(/\/ticket\/search\/\?text=.*/, { results: [], dropped: 2 });

    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');

    await waitUntil(() => !!el.shadowRoot.querySelector('.no-results'));
    expect(el.shadowRoot.querySelector('.no-results').textContent).to.contain(
      'No matches in tickets you can access'
    );

    // the count doesn't carry over to the next search
    clearMockGets();
    mockGET(/\/ticket\/search\/\?text=.*/, { results: [], dropped: 0 });
    await setQuery(el, 'help me');
    await pressKey(el, 'Enter');

    await waitUntil(
      () =>
        el.shadowRoot.querySelector('.no-results')?.textContent.trim() ===
        'No matches found'
    );
  });

  it('joins with & when the endpoint already has a query string', async () => {
    // only the correctly-joined URL is mocked, so results can only load if
    // the endpoint's existing params were preserved
    mockGET(/\/ticket\/search\/\?scope=all&text=.*/, RESPONSE);

    const el = await createSearch();
    el.endpoint = '/ticket/search/?scope=all';
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);

    expect(getResults(el).length).to.equal(3);
  });

  it('invalidates results when the query changes', async () => {
    const el = await createSearch();
    await setQuery(el, 'help');
    await pressKey(el, 'Enter');
    await waitUntil(() => getResults(el).length > 0);

    await setQuery(el, 'help me');
    expect(getResults(el).length).to.equal(0);
    const hint = el.shadowRoot.querySelector('.hint');
    expect(hint.textContent).to.contain('to search');
  });
});
