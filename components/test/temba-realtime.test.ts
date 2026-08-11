import { assert } from '@open-wc/testing';
import {
  setRealtimeContext,
  subscribeToContactHistory,
  subscribeToFlow,
  subscribeToNotifications,
  subscribeToOrganization
} from '../src/live/Realtime';
import { setSocketProvider, SocketProvider } from '../src/live/SocketService';
import { MockSocketProvider } from './utils.test';

describe('temba-realtime', () => {
  let mockSocket: MockSocketProvider;
  let previousProvider: SocketProvider;

  beforeEach(() => {
    mockSocket = new MockSocketProvider();
    previousProvider = setSocketProvider(mockSocket);
  });

  afterEach(() => {
    setRealtimeContext(null);
    setSocketProvider(previousProvider);
  });

  it('subscribes to notifications immediately when context is known', () => {
    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });

    const received = [];
    subscribeToNotifications((notification) => received.push(notification));

    assert.deepEqual(mockSocket.activeChannels(), [
      'notifications:org-uuid:user-uuid'
    ]);

    mockSocket.publish('notifications:org-uuid:user-uuid', {
      type: 'export:finished',
      url: '/notification/read/1/'
    });
    assert.equal(received.length, 1);
    assert.equal(received[0].type, 'export:finished');
  });

  it('queues notification subscriptions until context arrives', (done) => {
    let subscribed = false;
    subscribeToNotifications(
      () => {},
      () => {
        subscribed = true;
      }
    );

    // nothing yet, we don't know our channel
    assert.deepEqual(mockSocket.activeChannels(), []);

    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });
    assert.deepEqual(mockSocket.activeChannels(), [
      'notifications:org-uuid:user-uuid'
    ]);

    // the mock confirms subscriptions asynchronously
    setTimeout(() => {
      assert.isTrue(subscribed);
      done();
    }, 0);
  });

  it('subscribes to the current organization when context is known', () => {
    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });
    const received = [];
    subscribeToOrganization((event) => received.push(event));

    assert.deepEqual(mockSocket.activeChannels(), ['org:org-uuid']);
    mockSocket.serverPublish('org:org-uuid', {
      type: 'asset_changed',
      asset: { type: 'flow', uuid: 'flow-1', name: 'Registration' }
    });
    assert.equal(received[0].asset.name, 'Registration');
  });

  it('never subscribes when unsubscribed while pending', () => {
    const sub = subscribeToNotifications(() => {});
    sub.unsubscribe();

    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });
    assert.deepEqual(mockSocket.activeChannels(), []);
  });

  it('unsubscribes an activated pending subscription', () => {
    const sub = subscribeToNotifications(() => {});
    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });
    assert.deepEqual(mockSocket.activeChannels(), [
      'notifications:org-uuid:user-uuid'
    ]);

    sub.unsubscribe();
    assert.deepEqual(mockSocket.activeChannels(), []);
  });

  it('subscribes to contact history without context', () => {
    subscribeToContactHistory('contact-uuid', null, () => {});
    subscribeToContactHistory('contact-uuid', 'ticket-uuid', () => {});

    assert.deepEqual(mockSocket.activeChannels(), [
      'history:contact-uuid',
      'history:contact-uuid:ticket-uuid'
    ]);
  });

  it('subscribes to a flow without context', () => {
    const received = [];
    subscribeToFlow('flow-uuid', (event) => received.push(event));

    assert.deepEqual(mockSocket.activeChannels(), ['flow:flow-uuid']);
    mockSocket.serverPublish('flow:flow-uuid', { type: 'activity' });
    assert.deepEqual(received, [{ type: 'activity' }]);
  });
});
