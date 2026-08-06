import { assert, expect } from '@open-wc/testing';
import * as sinon from 'sinon';
import { CustomEventType } from '../src/interfaces';
import { TriggerList } from '../src/list/TriggerList';
import { getComponent } from './utils.test';

const TAG = 'temba-trigger-list';
const getTriggerList = async (attrs: any = {}, width = 700, height = 0) => {
  return (await getComponent(TAG, attrs, '', width, height)) as TriggerList;
};

// a plain click with no modifier keys, carrying the stopPropagation /
// preventDefault spies the handler is expected to call
const makeClick = (over: any = {}) =>
  ({
    metaKey: false,
    ctrlKey: false,
    stopPropagation: sinon.spy(),
    preventDefault: sinon.spy(),
    ...over
  }) as any;

/** Let the post-render pill-fit measurement converge — each pass is
 * a rAF followed by the re-render it may trigger. */
const settlePills = async (list: TriggerList) => {
  for (let i = 0; i < 6; i++) {
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
    await list.updateComplete;
  }
};

const trigger = (over: any = {}) => ({
  id: 101,
  type: 'keyword',
  flow: { uuid: 'flow-1', name: 'Registration' },
  channel: null,
  groups: [{ uuid: 'group-1', name: 'Farmers' }],
  exclude_groups: [],
  contacts: [],
  keywords: ['join', 'start'],
  match_type: 'F',
  created_on: '2026-05-11T09:12:00.000000Z',
  ...over
});

describe('temba-trigger-list', () => {
  it('can be created', async () => {
    const list: TriggerList = await getTriggerList();
    assert.instanceOf(list, TriggerList);
    // triggers have no uuid — rows key off the numeric id
    expect(list.valueKey).to.equal('id');
  });

  it('keeps rows event-only (no row href)', async () => {
    const list: TriggerList = await getTriggerList();
    // triggers open in an update modal — the host handles
    // temba-row-click, so rows must not navigate on their own
    expect((list as any).getRowHref(trigger())).to.be.null;
  });

  it('maps each trigger type to its icon', async () => {
    const list: TriggerList = await getTriggerList();
    expect((list as any).getRowIcon(trigger())).to.equal(
      'message-check-square'
    );
    expect((list as any).getRowIcon(trigger({ type: 'schedule' }))).to.equal(
      'calendar'
    );
    expect((list as any).getRowIcon(trigger({ type: 'missed_call' }))).to.equal(
      'phone-hang-up'
    );
    // an unknown type falls back to the generic trigger icon
    expect((list as any).getRowIcon(trigger({ type: 'wobble' }))).to.equal(
      'signal-01'
    );
  });

  it('fires a row click for the host to open the update modal', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [trigger()];
    list.requestUpdate();
    await list.updateComplete;

    const rowClicks: any[] = [];
    const redirects: any[] = [];
    list.addEventListener(CustomEventType.RowClick, (e: any) =>
      rowClicks.push(e.detail)
    );
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      redirects.push(e.detail)
    );

    const row = list.shadowRoot.querySelector('tr.row') as HTMLElement;
    row.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    expect(rowClicks).to.have.length(1);
    expect(rowClicks[0].item.id).to.equal(101);
    // no navigation — the host owns what happens next
    expect(redirects).to.have.length(0);
  });

  it('navigates to the flow when the flow pill is clicked', async () => {
    const list: TriggerList = await getTriggerList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handlePillClick('/flow/editor/flow-1/', event);

    // the row's modal click must not also fire
    expect(event.stopPropagation.called).to.be.true;
    expect(fired).to.have.length(1);
    expect(fired[0].url).to.equal('/flow/editor/flow-1/');
  });

  it('opens a pill target in a new tab on meta/ctrl-click', async () => {
    const list: TriggerList = await getTriggerList();
    const openStub = sinon.stub(window, 'open');
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    try {
      (list as any).handlePillClick(
        '/contact/group/group-1/',
        makeClick({ metaKey: true })
      );

      expect(openStub.calledWith('/contact/group/group-1/', '_blank')).to.be
        .true;
      // no in-app redirect when opening a new tab
      expect(fired).to.have.length(0);
    } finally {
      openStub.restore();
    }
  });

  it('refuses an unsafe pill href', async () => {
    const list: TriggerList = await getTriggerList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handlePillClick('//evil.com/x', event);

    // still swallows the click so the row doesn't open its modal...
    expect(event.stopPropagation.called).to.be.true;
    // ...but no redirect fires
    expect(fired).to.have.length(0);
  });

  it('intercepts a real click on a rendered group pill', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [trigger()];
    list.requestUpdate();
    await list.updateComplete;

    const pill = list.shadowRoot.querySelector(
      'temba-label[type="group"]'
    ) as HTMLElement;
    expect(pill, 'group pill rendered').to.exist;

    const redirects: any[] = [];
    const rowClicks: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      redirects.push(e.detail)
    );
    list.addEventListener(CustomEventType.RowClick, (e: any) =>
      rowClicks.push(e.detail)
    );

    pill.dispatchEvent(
      new MouseEvent('click', { bubbles: true, composed: true })
    );

    // the pill navigates, and the row's modal click is suppressed
    expect(redirects).to.have.length(1);
    expect(redirects[0].url).to.equal('/contact/group/group-1/');
    expect(rowClicks, 'row click suppressed').to.have.length(0);
  });

  it('renders keyword pills with the match-type lead-in', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [trigger()];
    list.requestUpdate();
    await list.updateComplete;

    const details = list.shadowRoot.querySelector('.details') as HTMLElement;
    // every trigger row leads with a word at the type-name weight
    expect(details.querySelector('.type-name').textContent.trim()).to.equal(
      'Message'
    );
    expect(details.querySelector('.lead-in').textContent.trim()).to.equal(
      'starts with'
    );
    const pills = details.querySelectorAll('temba-label[type="keyword"]');
    expect(pills).to.have.length(2);
    expect(pills[0].textContent.trim()).to.equal('join');

    // an exact-match trigger reads "matches" instead
    (list as any).items = [trigger({ match_type: 'O' })];
    list.requestUpdate();
    await list.updateComplete;
    expect(
      list.shadowRoot.querySelector('.details .lead-in').textContent.trim()
    ).to.equal('matches');
  });

  it('renders the schedule display, or not-scheduled when paused', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({
        type: 'schedule',
        keywords: null,
        schedule: {
          repeat_period: 'W',
          display: 'each week on Monday',
          next_fire: '2026-07-15T14:00:00.000000Z'
        }
      })
    ];
    list.requestUpdate();
    await list.updateComplete;

    let cells = list.shadowRoot.querySelectorAll('tr.row td');
    // the trigger cell is the first column after the checkbox, led by
    // the type-weight "Scheduled"
    expect(cells[1].textContent).to.contain('Scheduled');
    expect(cells[1].textContent).to.contain('each week on Monday');

    // a schedule with no next fire reads as not scheduled
    (list as any).items = [
      trigger({
        type: 'schedule',
        keywords: null,
        schedule: { repeat_period: 'O', display: '', next_fire: null }
      })
    ];
    list.requestUpdate();
    await list.updateComplete;
    cells = list.shadowRoot.querySelectorAll('tr.row td');
    expect(cells[1].textContent).to.contain('Not scheduled');
  });

  it('states the type name only when there are no details', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({ id: 1, type: 'new_conversation', keywords: null }),
      trigger({ id: 2 })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const rows = list.shadowRoot.querySelectorAll('tr.row');
    // a detail-less type is named outright — its icon alone is too
    // subtle to carry the type
    expect(rows[0].querySelectorAll('td')[1].textContent).to.contain(
      'New Conversation'
    );
    // a keyword trigger's details speak for themselves
    expect(rows[1].querySelectorAll('td')[1].textContent).to.not.contain(
      'Keyword'
    );
  });

  it('ellipsizes long detail text instead of clipping', async () => {
    // narrow enough that the schedule display can't fit
    const list: TriggerList = await getTriggerList({}, 560);
    (list as any).items = [
      trigger({
        type: 'schedule',
        keywords: null,
        schedule: {
          repeat_period: 'W',
          display:
            'each week on Monday, Tuesday, Wednesday, Thursday, Friday, Saturday',
          next_fire: '2026-07-15T14:00:00.000000Z'
        }
      })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const leadIn = list.shadowRoot.querySelector(
      '.details .lead-in'
    ) as HTMLElement;
    // the text overflows its box and carries its own ellipsis — flex
    // items don't inherit the cell wrapper's text-overflow
    expect(getComputedStyle(leadIn).textOverflow).to.equal('ellipsis');
    expect(getComputedStyle(leadIn).overflow).to.equal('hidden');
    expect(leadIn.scrollWidth).to.be.greaterThan(leadIn.clientWidth);
  });

  it('renders the referrer for referral triggers', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({ type: 'referral', keywords: null, referrer_id: 'summer-ads' })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const details = list.shadowRoot.querySelector('.details') as HTMLElement;
    expect(details.querySelector('.lead-in').textContent.trim()).to.equal(
      'from'
    );
    expect(details.textContent).to.contain('summer-ads');
  });

  it('renders channel and excluded-group pills', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({
        channel: { uuid: 'chan-1', name: 'WhatsApp Main', icon: 'channel-wa' },
        exclude_groups: [{ uuid: 'group-2', name: 'Staff' }]
      })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const channelPill = list.shadowRoot.querySelector(
      'temba-label[type="channel"]'
    );
    expect(channelPill, 'channel pill rendered').to.exist;
    expect(channelPill.textContent.trim()).to.equal('WhatsApp Main');

    // the channel pill leads the filters cell (the column after the
    // checkbox and trigger cells)
    const filtersCell = list.shadowRoot.querySelectorAll('tr.row td')[2];
    const pills = filtersCell.querySelector('.pills');
    expect(pills.firstElementChild.getAttribute('type')).to.equal('channel');

    // included and excluded groups carry distinct icons, and the
    // excluded one is tinted via the exclude class
    const groupPills = list.shadowRoot.querySelectorAll(
      'temba-label[type="group"]'
    );
    expect(groupPills).to.have.length(2);
    expect(groupPills[0].getAttribute('icon')).to.equal('users-check');
    expect(groupPills[0].classList.contains('exclude')).to.be.false;
    expect(groupPills[1].getAttribute('icon')).to.equal('users-x');
    expect(groupPills[1].classList.contains('exclude')).to.be.true;
  });

  it('folds filter pills past the cap into a +N summary', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({
        groups: [
          { uuid: 'g-1', name: 'Farmers' },
          { uuid: 'g-2', name: 'Doctors' },
          { uuid: 'g-3', name: 'Teachers' },
          { uuid: 'g-4', name: 'Drivers' }
        ],
        exclude_groups: [{ uuid: 'g-5', name: 'Staff' }]
      })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const filtersCell = list.shadowRoot.querySelectorAll('tr.row td')[2];
    const pills = filtersCell.querySelectorAll('temba-label');
    // three real pills plus the summary
    expect(pills).to.have.length(4);
    expect(pills[3].classList.contains('overflow')).to.be.true;
    expect(pills[3].textContent.trim()).to.equal('+2');
    // the tooltip names what's hidden, keeping exclusions marked
    expect(pills[3].getAttribute('title')).to.equal('Drivers, not Staff');
  });

  it('keeps keyword pills from collapsing to bare chrome', async () => {
    // narrow enough that the keyword row can't fit everything
    const list: TriggerList = await getTriggerList({}, 560);
    (list as any).items = [
      trigger({ keywords: ['registration', 'subscription', 'notification'] })
    ];
    list.requestUpdate();
    await settlePills(list);

    const pills = list.shadowRoot.querySelectorAll(
      'temba-label[type="keyword"]'
    );
    pills.forEach((p: any) => {
      // long keywords are the shrinkable ones, floored at 4em so a
      // squeezed pill keeps a few identifying characters
      expect(p.classList.contains('wide')).to.be.true;
      expect(p.getBoundingClientRect().width).to.be.greaterThan(40);
    });

    // short keywords never shrink at all
    (list as any).items = [trigger({ keywords: ['go', 'hi', 'join'] })];
    list.requestUpdate();
    await settlePills(list);
    list.shadowRoot
      .querySelectorAll('temba-label[type="keyword"]')
      .forEach((p: any) => {
        expect(p.classList.contains('wide')).to.be.false;
        expect(getComputedStyle(p).flexShrink).to.equal('0');
      });
  });

  it('folds pills down to what actually fits instead of clipping', async () => {
    // a narrow list whose trigger column cannot fit three pills
    const list: TriggerList = await getTriggerList({}, 560);
    (list as any).items = [
      trigger({ keywords: ['join', 'stop', 'help', 'info'] })
    ];
    list.requestUpdate();
    await settlePills(list);

    const pillBox = list.shadowRoot.querySelector(
      '.pills[data-fit]'
    ) as HTMLElement;
    // the budget has converged — nothing overflows the pill row
    expect(pillBox.scrollWidth).to.be.at.most(pillBox.clientWidth + 1);

    // fewer pills render than the static cap, and the +N summary
    // accounts for every hidden keyword
    const visible = pillBox.querySelectorAll('temba-label[type="keyword"]');
    expect(visible.length).to.be.lessThan(3);
    const overflow = pillBox.querySelector('temba-label.overflow');
    expect(overflow.textContent.trim()).to.equal(`+${4 - visible.length}`);
  });

  it('does not remeasure pills on unrelated re-renders', async () => {
    const list: TriggerList = await getTriggerList({}, 560);
    (list as any).items = [
      trigger({ keywords: ['join', 'stop', 'help', 'info'] })
    ];
    list.requestUpdate();
    await settlePills(list);

    const budgets = new Map((list as any).pillBudgets);

    // a re-render with no item/geometry change — what a scroll-state
    // update looks like — must not schedule a measure pass
    list.requestUpdate();
    await list.updateComplete;

    expect((list as any).pillMeasureFrame).to.equal(0);
    expect((list as any).pillBudgets).to.deep.equal(budgets);
  });

  it('keeps budgets on a resize that leaves column widths unchanged', async () => {
    // at 560 the table is already at its column minimums and scrolls
    // horizontally — the columns can't get any narrower
    const list: TriggerList = await getTriggerList({}, 560);
    (list as any).items = [
      trigger({ keywords: ['join', 'stop', 'help', 'info'] })
    ];
    list.requestUpdate();
    await settlePills(list);

    const before = new Map((list as any).pillBudgets);
    expect(before.size, 'folding happened').to.be.greaterThan(0);

    // widen the page slightly — the host resizes, but the columns
    // stay pinned at their minimums, so no cell width changes and no
    // budget may be reset (a reset re-renders and flashes)
    (list.parentElement as HTMLElement).style.width = '585px';
    // wait out the resize debounce, then let any recompute settle
    await new Promise((resolve) => setTimeout(resolve, 300));
    await settlePills(list);

    expect((list as any).pillBudgets).to.deep.equal(before);
  });

  it('folds keyword pills past the cap into a +N summary', async () => {
    const list: TriggerList = await getTriggerList();
    (list as any).items = [
      trigger({ keywords: ['join', 'start', 'begin', 'go', 'enroll'] })
    ];
    list.requestUpdate();
    await list.updateComplete;

    const triggerCell = list.shadowRoot.querySelectorAll('tr.row td')[1];
    const keywordPills = triggerCell.querySelectorAll(
      'temba-label[type="keyword"]'
    );
    expect(keywordPills).to.have.length(3);
    const overflow = triggerCell.querySelector('temba-label.overflow');
    expect(overflow.textContent.trim()).to.equal('+2');
    expect(overflow.getAttribute('title')).to.equal('go, enroll');
  });
});
