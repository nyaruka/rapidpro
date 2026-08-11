import { assert } from '@open-wc/testing';
import { spy } from 'sinon';
import { Contact } from '../src/interfaces';
import { Events } from '../src/events/eventRenderers';
import {
  applyContactEvent,
  CONTACT_STATE_TYPES,
  resetContactWatches,
  watchContact
} from '../src/live/ContactWatch';
import { setSocketProvider, SocketProvider } from '../src/live/SocketService';
import { getStore } from '../src/store/Store';
import {
  clearMockGets,
  loadStore,
  mockGET,
  MockSocketProvider,
  waitForCondition
} from './utils.test';

const CONTACT = 'contact-dave-active';
const CHANNEL = `history:${CONTACT}`;

// fetches the watcher made for the contact, ignoring everything else the
// store pulls down
const contactFetches = (getUrl: any) =>
  getUrl.getCalls().filter((call: any) => call.args[0].includes(CONTACT));

describe('ContactWatch', () => {
  let mockSocket: MockSocketProvider;
  let previousProvider: SocketProvider;
  let getUrl: any;

  beforeEach(async () => {
    mockSocket = new MockSocketProvider();
    previousProvider = setSocketProvider(mockSocket);
    clearMockGets();
    mockGET(
      /\/api\/v2\/contacts\.json\?expand_urns=true&urn_order=priority&uuid=contact-dave-active/,
      '/test-assets/contacts/contact-dave-active'
    );
    await loadStore();
    getUrl = spy(getStore(), 'getUrl');
  });

  afterEach(() => {
    getUrl.restore();
    resetContactWatches();
    setSocketProvider(previousProvider);
  });

  describe('onSubscribed', () => {
    it('tells a watcher when the channel goes live', async () => {
      let subscribed = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => subscribed++
      );

      await waitForCondition(() => subscribed === 1);
      assert.deepEqual(mockSocket.activeChannels(), [CHANNEL]);
    });

    it('gives a late joiner its own catch-up call', async () => {
      let first = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => first++
      );
      await waitForCondition(() => first === 1);

      // joining an already-live channel would otherwise mean waiting for a
      // reconnect to hear anything
      let second = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => second++
      );

      await waitForCondition(() => second === 1);
      assert.equal(first, 1, 'existing watcher should not be told again');
    });

    it('does not call it once unsubscribed', async () => {
      let subscribed = 0;
      const watch = watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => subscribed++
      );
      watch.unsubscribe();

      await waitForCondition(() => mockSocket.activeChannels().length === 0);
      assert.equal(subscribed, 0);
    });
  });

  describe('stream consumers', () => {
    it('holds no contact and fetches nothing for wildcard watchers alone', async () => {
      const events: any[] = [];
      let subscribed = 0;
      watchContact(
        CONTACT,
        '*',
        (event) => events.push(event),
        () => subscribed++
      );
      await waitForCondition(() => subscribed === 1);

      // a state event that would normally keep a held contact current
      mockSocket.serverPublish(CHANNEL, {
        type: Events.CONTACT_NAME_CHANGED,
        name: 'David J. Matthews'
      });

      // events still stream through, but nothing was fetched to apply them to
      assert.equal(events.length, 1);
      assert.deepEqual(contactFetches(getUrl), []);
    });

    it('does not refetch for a stream-only entry on a urn change', async () => {
      let subscribed = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => subscribed++
      );
      await waitForCondition(() => subscribed === 1);

      mockSocket.serverPublish(CHANNEL, {
        type: Events.CONTACT_URNS_CHANGED,
        urns: ['tel:+12065551212']
      });

      // the debounced refetch would have landed by now
      await waitForCondition(() => true, 1, 200);
      assert.deepEqual(contactFetches(getUrl), []);
    });

    it('fetches once a state watcher joins a stream-only entry', async () => {
      let subscribed = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => subscribed++
      );
      await waitForCondition(() => subscribed === 1);
      assert.deepEqual(contactFetches(getUrl), []);

      let delivered: Contact = null;
      watchContact(CONTACT, CONTACT_STATE_TYPES, (_event, contact) => {
        delivered = contact;
      });

      await waitForCondition(() => !!delivered);
      assert.equal(delivered.name, 'Dave Matthews');
      assert.equal(contactFetches(getUrl).length, 1);
    });

    it('fetches again for a state watcher joining after the last one left', async () => {
      let subscribed = 0;
      watchContact(
        CONTACT,
        '*',
        () => undefined,
        () => subscribed++
      );
      await waitForCondition(() => subscribed === 1);

      let delivered: Contact = null;
      const state = watchContact(
        CONTACT,
        CONTACT_STATE_TYPES,
        (_event, contact) => {
          delivered = contact;
        }
      );
      await waitForCondition(() => !!delivered);
      assert.equal(contactFetches(getUrl).length, 1);

      // the details pane closes, but the chat's stream keeps the entry alive
      state.unsubscribe();

      // nothing holds that contact current any more, so a state watcher
      // joining later has to fetch rather than be primed with what we last
      // saw and stopped maintaining
      let rejoined: Contact = null;
      watchContact(CONTACT, CONTACT_STATE_TYPES, (_event, contact) => {
        rejoined = contact;
      });

      await waitForCondition(() => !!rejoined);
      assert.equal(contactFetches(getUrl).length, 2);
    });
  });

  describe('applyContactEvent', () => {
    it('applies a flow change', () => {
      const contact = { flow: null } as Contact;
      applyContactEvent(contact, {
        type: Events.CONTACT_FLOW_CHANGED,
        flow: { uuid: 'flow-1', name: 'Registration' }
      });
      assert.equal(contact.flow.name, 'Registration');

      applyContactEvent(contact, {
        type: Events.CONTACT_FLOW_CHANGED,
        flow: null
      });
      assert.isNull(contact.flow);
    });

    it('only moves last seen forward', () => {
      const contact = { last_seen_on: '2026-01-02T00:00:00Z' } as Contact;

      applyContactEvent(contact, {
        type: Events.CONTACT_LAST_SEEN_CHANGED,
        last_seen_on: '2026-01-01T00:00:00Z'
      });
      assert.equal(contact.last_seen_on, '2026-01-02T00:00:00Z');

      applyContactEvent(contact, {
        type: Events.CONTACT_LAST_SEEN_CHANGED,
        last_seen_on: '2026-01-03T00:00:00Z'
      });
      assert.equal(contact.last_seen_on, '2026-01-03T00:00:00Z');
    });

    it('ignores events it has no applier for', () => {
      const contact = { name: 'Dave' } as Contact;
      assert.isUndefined(
        applyContactEvent(contact, { type: 'msg_created', msg: {} })
      );
      assert.equal(contact.name, 'Dave');
    });

    it('tolerates a missing contact', () => {
      assert.isUndefined(
        applyContactEvent(null, {
          type: Events.CONTACT_NAME_CHANGED,
          name: 'Dave'
        })
      );
    });
  });
});
