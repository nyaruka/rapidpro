import { expect, fixture, html } from '@open-wc/testing';
import {
  renderEventTooltip,
  renderTicketAssigneeChanged
} from '../src/events/eventRenderers';
import { TicketEvent } from '../src/events';

// Build a TicketEvent fixture. The user variance (Chat.ts User
// requires uuid; interfaces.ts User declares it optional) lives
// only on the _user / assignee slots — keep the rest of the
// overrides strictly typed so typos still fail the build.
const makeEvent = (
  overrides: Partial<Omit<TicketEvent, '_user' | 'assignee'>> & {
    _user?: any;
    assignee?: any;
  } = {}
): TicketEvent => {
  return {
    type: 'ticket_assignee_changed',
    uuid: 'evt-1',
    created_on: new Date(),
    ticket: { uuid: 'ticket-1' },
    ...overrides
  } as TicketEvent;
};

// assignee changes render as a self-contained ticket pill whose text
// is the assignee (or "Unassigned"); the hover tooltip only adds
// what the pill can't show — the acting user (avatar + name) above
// the detailed timestamp
const getPill = (el: Element) => el.querySelector('temba-label');

const renderTooltip = async (event: TicketEvent): Promise<HTMLElement> => {
  return fixture(html`<div>${renderEventTooltip(event)}</div>`);
};

describe('renderTicketAssigneeChanged', () => {
  it('renders the assignee name in the pill', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' },
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const el = await fixture(
      html`<div>${renderTicketAssigneeChanged(event)}</div>`
    );
    expect(el.textContent).to.contain('Sally Sue');
  });

  it('renders "Unassigned" when assignee is absent', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' }
    });

    const el = await fixture(
      html`<div>${renderTicketAssigneeChanged(event)}</div>`
    );
    expect(el.textContent).to.contain('Unassigned');
  });

  it('carries no native title on the pill (the rich tooltip replaces it)', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' },
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const el = await fixture(
      html`<div>${renderTicketAssigneeChanged(event)}</div>`
    );
    expect(getPill(el).hasAttribute('title')).to.equal(false);
  });

  it('links the pill to the ticket', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' },
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const el: HTMLElement = await fixture(
      html`<div>${renderTicketAssigneeChanged(event)}</div>`
    );
    const link = el.querySelector('a');
    expect(link.getAttribute('href')).to.equal('/ticket/all/open/ticket-1/');
  });
});

describe('renderEventTooltip (ticket assignment)', () => {
  it('shows the acting user with an avatar above the timestamp', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' },
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const tip = await renderTooltip(event);
    expect(tip.textContent).to.contain('Adam Ant');
    expect(tip.querySelectorAll('temba-user').length).to.equal(1);
    expect(tip.querySelector('temba-date')).to.not.equal(null);
  });

  it('does not repeat the assignee (already visible in the pill)', async () => {
    const event = makeEvent({
      _user: { uuid: 'u-adam', name: 'Adam Ant', email: 'adam@example.com' },
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const tip = await renderTooltip(event);
    expect(tip.textContent).to.not.contain('Sally Sue');
  });

  it('shows only the timestamp when there is no acting user', async () => {
    const event = makeEvent({
      assignee: { uuid: 'u-sally', name: 'Sally Sue', email: 's@example.com' }
    });

    const tip = await renderTooltip(event);
    expect(tip.querySelectorAll('temba-user').length).to.equal(0);
    expect(tip.textContent).to.not.contain('Sally Sue');
    expect(tip.querySelector('temba-date')).to.not.equal(null);
  });
});
