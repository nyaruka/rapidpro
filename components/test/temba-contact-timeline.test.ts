import { assert, expect } from '@open-wc/testing';
import { ContactTimeline } from '../src/live/ContactTimeline';
import {
  clearMockGets,
  getComponent,
  loadStore,
  mockGET,
  waitForCondition
} from './utils.test';

const TAG = 'temba-contact-timeline';

// the older-events pager dot exposes the localized show-older label, which we
// use as a stable hook rather than coupling tests to internal class names
const SHOW_OLDER_LABEL = 'Show older events';
const SHOW_MORE_LABEL = 'Show more upcoming events';

const FIRST_PAGE = {
  now: '2024-06-01T12:00:00+00:00',
  campaigns: [
    { uuid: 'camp-1', name: 'Onboarding', url: '/campaign/read/camp-1/' }
  ],
  future: [
    {
      type: 'scheduled_broadcast',
      scheduled: '2024-06-05T12:00:00+00:00',
      repeat_period: 'D',
      message: 'A scheduled reminder'
    },
    {
      type: 'scheduled_trigger',
      scheduled: '2024-06-07T12:00:00+00:00',
      repeat_period: 'W',
      flow: { uuid: 'flow-2', name: 'Survey' }
    },
    {
      type: 'campaign_event',
      scheduled: '2024-06-10T12:00:00+00:00',
      campaign: { uuid: 'camp-1', name: 'Onboarding' },
      flow: { uuid: 'flow-1', name: 'Welcome' }
    }
  ],
  past: [
    {
      type: 'sent_broadcast',
      scheduled: '2024-05-20T12:00:00+00:00',
      message: 'Welcome aboard'
    },
    {
      type: 'campaign_event',
      scheduled: '2024-05-10T12:00:00+00:00',
      campaign: { uuid: 'camp-1', name: 'Onboarding' },
      message: 'Day 1 tip'
    }
  ],
  next_before: '2024-05-10T12:00:00+00:00',
  next_after: '2024-06-10T12:00:00+00:00'
};

const OLDER_PAGE = {
  now: '2024-06-01T12:00:00+00:00',
  future: [],
  past: [
    {
      type: 'campaign_event',
      scheduled: '2024-04-01T12:00:00+00:00',
      campaign: { uuid: 'camp-2', name: 'Follow Up' },
      message: 'An older event'
    }
  ],
  next_before: null
};

const NEWER_PAGE = {
  now: '2024-06-01T12:00:00+00:00',
  future: [
    {
      type: 'campaign_event',
      scheduled: '2024-06-20T12:00:00+00:00',
      campaign: { uuid: 'camp-3', name: 'Reactivation' },
      message: 'A newer projected event'
    }
  ],
  past: [],
  next_after: null
};

const getEvents = async (data: any = FIRST_PAGE): Promise<ContactTimeline> => {
  // paged requests (?before= / ?after=) take precedence over the first-page mock
  mockGET(/contact\/timeline\/.*before=/, OLDER_PAGE);
  mockGET(/contact\/timeline\/.*after=/, NEWER_PAGE);
  mockGET(/contact\/timeline\//, data);

  const events = (await getComponent(
    TAG,
    { contact: 'contact-dave-active' },
    '',
    600
  )) as ContactTimeline;

  await waitForCondition(() => !!events.data);
  await events.updateComplete;
  return events;
};

describe(TAG, () => {
  beforeEach(() => {
    // mockGET appends to a module-level list that getResponse scans first-match;
    // clearing between tests prevents a prior payload from leaking into a later
    // test that mocks the same URL pattern (e.g. the empty-state test)
    clearMockGets();
  });

  it('renders a timeline of past and future events', async () => {
    await loadStore();
    const events = await getEvents();
    assert.instanceOf(events, ContactTimeline);

    const root = events.shadowRoot;
    expect(root.querySelector('.timeline')).to.not.equal(null);

    // 3 future + 2 past events, each filled or outlined accordingly
    expect(root.querySelectorAll('.dot.future').length).to.equal(3);
    expect(root.querySelectorAll('.dot.past').length).to.equal(2);

    // a single "now" marker sits between them
    expect(root.querySelectorAll('.dot.now').length).to.equal(1);
  });

  it('syntax highlights expressions in message events', async () => {
    await loadStore();
    const events = await getEvents({
      ...FIRST_PAGE,
      future: [
        {
          type: 'campaign_event',
          scheduled: '2024-06-10T12:00:00+00:00',
          campaign: { uuid: 'camp-1', name: 'Onboarding' },
          message:
            'Time to refill @fields.patient_medications. Please reach out to your pharmacist.'
        }
      ]
    });

    // message text is rendered through the expression highlighter (past
    // message events render the same way, so find the future one by text)
    const highlight = Array.from(
      events.shadowRoot.querySelectorAll(
        '.title-text temba-expression-highlight'
      )
    ).find((ele) =>
      ele.textContent.includes('@fields.patient_medications')
    ) as any;
    expect(highlight).to.not.equal(undefined);
    expect(highlight.textContent.trim()).to.equal(
      'Time to refill @fields.patient_medications. Please reach out to your pharmacist.'
    );

    // and the expression inside it is tokenized
    await highlight.updateComplete;
    const identifier = highlight.shadowRoot.querySelector('.tok-id');
    expect(identifier).to.not.equal(null);
    expect(identifier.textContent).to.contain('fields.patient_medications');
  });

  it('renders an empty state when there are no events', async () => {
    await loadStore();
    const events = await getEvents({
      now: '2024-06-01T12:00:00+00:00',
      future: [],
      past: [],
      next_before: null
    });

    const empty = events.shadowRoot.querySelector('.empty');
    expect(empty).to.not.equal(null);
    expect(events.shadowRoot.querySelector('.timeline')).to.equal(null);

    // the empty state explains how events end up here and links to campaigns
    expect(empty.querySelector('.empty-help')).to.not.equal(null);
    const link = empty.querySelector('.empty-link') as HTMLAnchorElement;
    expect(link).to.not.equal(null);
    expect(link.getAttribute('href')).to.equal('/campaign/');
  });

  it('pages back through older events', async () => {
    await loadStore();
    const events = await getEvents();

    // the pager is shown while there are older events to load
    const pager = events.shadowRoot.querySelector(
      `button[aria-label="${SHOW_OLDER_LABEL}"]`
    ) as HTMLElement;
    expect(pager).to.not.equal(null);

    pager.click();
    await waitForCondition(
      () =>
        events.shadowRoot.querySelector(
          `button[aria-label="${SHOW_OLDER_LABEL}"]`
        ) === null
    );
    await events.updateComplete;

    // the older page is appended and the pager is gone
    expect(events.shadowRoot.querySelectorAll('.dot.past').length).to.equal(3);
  });

  it('hides the older-events pager when the cursor is null', async () => {
    await loadStore();
    const events = await getEvents({
      now: '2024-06-01T12:00:00+00:00',
      future: FIRST_PAGE.future,
      past: FIRST_PAGE.past,
      next_before: null
    });

    expect(
      events.shadowRoot.querySelector(
        `button[aria-label="${SHOW_OLDER_LABEL}"]`
      )
    ).to.equal(null);
  });

  it('fires a selection event when an event is clicked', async () => {
    await loadStore();
    const events = await getEvents();

    let selected: any = null;
    events.addEventListener('temba-selection', (e: CustomEvent) => {
      selected = e.detail;
    });

    const entry = events.shadowRoot.querySelector(
      '.event.clickable'
    ) as HTMLElement;
    entry.click();

    expect(selected).to.not.equal(null);
  });

  it('fires selection with the campaign url when a campaign pill is clicked', async () => {
    await loadStore();
    const events = await getEvents();

    let selected: any = null;
    events.addEventListener('temba-selection', (e: CustomEvent) => {
      selected = e.detail;
    });

    const pill = events.shadowRoot.querySelector(
      '.campaign-pill'
    ) as HTMLElement;
    expect(pill).to.not.equal(null);
    pill.click();

    expect(selected).to.not.equal(null);
    expect(selected.uuid).to.equal('camp-1');
    expect(selected.url).to.equal('/campaign/read/camp-1/');
  });

  it('fires selection with the campaign url when a campaign pill is activated via the Enter key', async () => {
    await loadStore();
    const events = await getEvents();

    let selected: any = null;
    events.addEventListener('temba-selection', (e: CustomEvent) => {
      selected = e.detail;
    });

    const pill = events.shadowRoot.querySelector(
      '.campaign-pill'
    ) as HTMLElement;
    expect(pill).to.not.equal(null);
    pill.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    );

    expect(selected).to.not.equal(null);
    expect(selected.uuid).to.equal('camp-1');
    expect(selected.url).to.equal('/campaign/read/camp-1/');
  });

  it('fires selection with the campaign url when a campaign pill is activated via the Space key', async () => {
    await loadStore();
    const events = await getEvents();

    let selected: any = null;
    events.addEventListener('temba-selection', (e: CustomEvent) => {
      selected = e.detail;
    });

    const pill = events.shadowRoot.querySelector(
      '.campaign-pill'
    ) as HTMLElement;
    expect(pill).to.not.equal(null);
    pill.dispatchEvent(
      new KeyboardEvent('keydown', { key: ' ', bubbles: true })
    );

    expect(selected).to.not.equal(null);
    expect(selected.uuid).to.equal('camp-1');
    expect(selected.url).to.equal('/campaign/read/camp-1/');
  });

  it('pages forward through newer upcoming events', async () => {
    await loadStore();
    const events = await getEvents();

    const pager = events.shadowRoot.querySelector(
      `button[aria-label="${SHOW_MORE_LABEL}"]`
    ) as HTMLElement;
    expect(pager).to.not.equal(null);

    pager.click();
    await waitForCondition(
      () =>
        events.shadowRoot.querySelector(
          `button[aria-label="${SHOW_MORE_LABEL}"]`
        ) === null
    );
    await events.updateComplete;

    // 3 originals + 1 newer-page event
    expect(events.shadowRoot.querySelectorAll('.dot.future').length).to.equal(
      4
    );
  });

  it('hides the newer-events pager when the cursor is null', async () => {
    await loadStore();
    const events = await getEvents({
      ...FIRST_PAGE,
      next_after: null
    });

    expect(
      events.shadowRoot.querySelector(`button[aria-label="${SHOW_MORE_LABEL}"]`)
    ).to.equal(null);
  });

  it('hides the pager and preserves data when a pager request fails', async () => {
    await loadStore();
    // override the default 200 mock for older pages with a 500
    clearMockGets();
    mockGET(/contact\/timeline\/.*before=/, {}, {}, '500');
    mockGET(/contact\/timeline\//, FIRST_PAGE);

    const events = (await getComponent(
      TAG,
      { contact: 'contact-dave-active' },
      '',
      600
    )) as ContactTimeline;
    await waitForCondition(() => !!events.data);
    await events.updateComplete;

    const initialPast = events.shadowRoot.querySelectorAll('.dot.past').length;
    expect(initialPast).to.equal(2);

    const pager = events.shadowRoot.querySelector(
      `button[aria-label="${SHOW_OLDER_LABEL}"]`
    ) as HTMLElement;
    pager.click();
    await waitForCondition(
      () =>
        events.shadowRoot.querySelector(
          `button[aria-label="${SHOW_OLDER_LABEL}"]`
        ) === null
    );
    await events.updateComplete;

    // prior data is intact, pager is gone
    expect(events.shadowRoot.querySelectorAll('.dot.past').length).to.equal(
      initialPast
    );
    expect(events.data).to.not.equal(null);
  });

  it('activates a clickable event row via the Enter key', async () => {
    await loadStore();
    const events = await getEvents();

    let selected: any = null;
    events.addEventListener('temba-selection', (e: CustomEvent) => {
      selected = e.detail;
    });

    const entry = events.shadowRoot.querySelector(
      '.event.clickable'
    ) as HTMLElement;
    entry.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    );

    expect(selected).to.not.equal(null);
  });

  it('fires details-changed with the upcoming event count', async () => {
    await loadStore();

    let detail: any = null;
    const handler = (e: CustomEvent) => {
      detail = e.detail;
    };
    document.addEventListener('temba-details-changed', handler);

    try {
      await getEvents({
        ...FIRST_PAGE,
        future_count: 7
      });
      expect(detail).to.not.equal(null);
      expect(detail.count).to.equal(7);
    } finally {
      document.removeEventListener('temba-details-changed', handler);
    }
  });

  it('does not fire details-changed during the contact-switch null gap', async () => {
    await loadStore();
    const events = await getEvents({
      ...FIRST_PAGE,
      future_count: 4
    });

    const dispatches: any[] = [];
    const handler = (e: CustomEvent) => {
      dispatches.push(e.detail);
    };
    document.addEventListener('temba-details-changed', handler);

    try {
      // mock a slow response so we can observe the null gap: re-setting
      // `contact` triggers updated() which nulls `data` before the new fetch
      // resolves. The null pass through updated('data') must NOT dispatch.
      events.contact = 'contact-other';
      await events.updateComplete;

      // any dispatch during the null window would carry count:0 - assert none
      // of the observed details have count:0
      for (const detail of dispatches) {
        expect(detail.count).to.not.equal(0);
      }
    } finally {
      document.removeEventListener('temba-details-changed', handler);
    }
  });
});
