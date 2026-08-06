import { expect, fixture, html } from '@open-wc/testing';
import { renderAirtimeCreatedEvent } from '../src/events/eventRenderers';
import { AirtimeCreatedEvent, AirtimeStatus } from '../src/events';

const makeEvent = (
  overrides: Partial<AirtimeCreatedEvent> = {}
): AirtimeCreatedEvent => {
  return {
    type: 'airtime_created',
    uuid: 'evt-1',
    created_on: new Date(),
    sender: 'tel:+250788111111',
    recipient: 'tel:+250788222222',
    currency: 'USD',
    amount: '1.50',
    ...overrides
  } as AirtimeCreatedEvent;
};

const withStatus = (status: AirtimeStatus): AirtimeCreatedEvent =>
  makeEvent({
    _status: { created_on: '2025-11-17T19:07:58.472259Z', status }
  });

// the airtime event renders as a self-contained "Airtime | <value>"
// pill; the value carries the amount while in flight or completed,
// and the terminal state otherwise
describe('renderAirtimeCreatedEvent', () => {
  it('renders the amount for in-flight statuses', async () => {
    for (const status of ['created', 'confirmed', 'submitted'] as const) {
      const el = await fixture(
        html`<div>${renderAirtimeCreatedEvent(withStatus(status))}</div>`
      );
      expect(el.textContent, status).to.contain('Airtime');
      expect(el.textContent, status).to.contain('1.50 USD');
    }
  });

  it('renders the amount for completed', async () => {
    const el = await fixture(
      html`<div>${renderAirtimeCreatedEvent(withStatus('completed'))}</div>`
    );
    expect(el.textContent).to.contain('Airtime');
    expect(el.textContent).to.contain('1.50 USD');
  });

  it('renders "failed" for terminal failure statuses', async () => {
    for (const status of ['rejected', 'cancelled', 'declined'] as const) {
      const el = await fixture(
        html`<div>${renderAirtimeCreatedEvent(withStatus(status))}</div>`
      );
      expect(el.textContent, status).to.contain('failed');
      expect(el.textContent, status).to.not.contain('1.50 USD');
    }
  });

  it('renders "reversed" for reversed (a previously completed transfer clawed back)', async () => {
    const el = await fixture(
      html`<div>${renderAirtimeCreatedEvent(withStatus('reversed'))}</div>`
    );
    expect(el.textContent).to.contain('reversed');
    expect(el.textContent).to.not.contain('failed');
  });

  it('renders the amount when _status is missing', async () => {
    const el = await fixture(
      html`<div>${renderAirtimeCreatedEvent(makeEvent())}</div>`
    );
    expect(el.textContent).to.contain('1.50 USD');
  });
});
