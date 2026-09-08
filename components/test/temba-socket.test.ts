import { assert, expect } from '@open-wc/testing';
import { SinonStub, stub } from 'sinon';
import { ConnectionState, SocketManager } from '../src/live/SocketService';
import { pageReloader, resetWorkspaceStale } from '../src/workspace';
import { clearMockGets, mockGET } from './utils.test';

class FakeSub {
  public handlers: { [event: string]: ((ctx: any) => void)[] } = {};
  public state = 'unsubscribed';
  public subscribeCalls = 0;
  public unsubscribeCalls = 0;
  public published: any[] = [];
  public denyPublishes = false;

  public publish(data: any): Promise<any> {
    if (this.denyPublishes) {
      return Promise.reject(new Error('permission denied'));
    }
    this.published.push(data);
    return Promise.resolve({});
  }

  public on(event: string, fn: (ctx: any) => void) {
    this.handlers[event] = this.handlers[event] || [];
    this.handlers[event].push(fn);
    return this;
  }

  public off(event: string, fn: (ctx: any) => void) {
    this.handlers[event] = (this.handlers[event] || []).filter(
      (handler) => handler !== fn
    );
    return this;
  }

  public subscribe() {
    this.subscribeCalls++;
    this.state = 'subscribed';
  }

  public unsubscribe() {
    this.unsubscribeCalls++;
    this.state = 'unsubscribed';
  }

  public emit(event: string, ctx: any) {
    (this.handlers[event] || []).forEach((handler) => handler(ctx));
  }
}

class FakeCentrifuge {
  public subs = new Map<string, FakeSub>();
  public removed: FakeSub[] = [];
  public published: { channel: string; data: any }[] = [];

  // creating the real client connects, so a fake starts where that leaves it
  public state = 'connecting';
  public handlers: { [event: string]: ((ctx: any) => void)[] } = {};

  public on(event: string, fn: (ctx: any) => void) {
    this.handlers[event] = this.handlers[event] || [];
    this.handlers[event].push(fn);
    return this;
  }

  // drives a connection transition as the server would
  public transition(state: string) {
    this.state = state;
    (this.handlers[state] || []).forEach((handler) => handler({}));
  }

  public publish(channel: string, data: any): Promise<any> {
    this.published.push({ channel, data });
    return Promise.resolve({});
  }

  public getSubscription(channel: string) {
    return this.subs.get(channel) || null;
  }

  public newSubscription(channel: string) {
    const sub = new FakeSub();
    this.subs.set(channel, sub);
    return sub;
  }

  public removeSubscription(sub: FakeSub) {
    this.removed.push(sub);
    this.subs.forEach((existing, channel) => {
      if (existing === sub) {
        this.subs.delete(channel);
      }
    });
  }
}

const createManager = () => {
  const fake = new FakeCentrifuge();
  let connections = 0;
  const manager = new SocketManager(() => {
    connections++;
    return fake as any;
  });
  return { fake, manager, connections: () => connections };
};

describe('SocketManager', () => {
  it('shares one connection and subscription across subscribers', () => {
    const { fake, manager, connections } = createManager();

    const seenA = [];
    const seenB = [];
    manager.subscribe('history:abc', (data) => seenA.push(data));
    manager.subscribe('history:abc', (data) => seenB.push(data));
    manager.subscribe('history:other', () => {});

    assert.equal(connections(), 1);
    assert.equal(fake.subs.size, 2);

    const sub = fake.subs.get('history:abc');
    assert.equal(sub.subscribeCalls, 1);

    sub.emit('publication', { data: { type: 'msg_created' } });
    assert.deepEqual(seenA, [{ type: 'msg_created' }]);
    assert.deepEqual(seenB, [{ type: 'msg_created' }]);
  });

  it('tears down the subscription when the last subscriber leaves', () => {
    const { fake, manager } = createManager();

    const first = manager.subscribe('history:abc', () => {});
    const second = manager.subscribe('history:abc', () => {});
    const sub = fake.subs.get('history:abc');

    first.unsubscribe();
    // safe to call twice, still counted once
    first.unsubscribe();
    assert.equal(sub.unsubscribeCalls, 0);

    second.unsubscribe();
    assert.equal(sub.unsubscribeCalls, 1);
    assert.deepEqual(fake.removed, [sub]);
  });

  it('stops delivering to unsubscribed handlers', () => {
    const { fake, manager } = createManager();

    const seenA = [];
    const seenB = [];
    const first = manager.subscribe('history:abc', (data) => seenA.push(data));
    manager.subscribe('history:abc', (data) => seenB.push(data));

    first.unsubscribe();
    fake.subs.get('history:abc').emit('publication', { data: 'hello' });

    assert.deepEqual(seenA, []);
    assert.deepEqual(seenB, ['hello']);
  });

  it('notifies late joiners on an already-live channel', (done) => {
    const { fake, manager } = createManager();

    manager.subscribe('history:abc', () => {});
    assert.equal(fake.subs.get('history:abc').state, 'subscribed');

    manager.subscribe(
      'history:abc',
      () => {},
      () => done()
    );
  });

  it('resubscribes a channel after full teardown', () => {
    const { fake, manager } = createManager();

    const first = manager.subscribe('history:abc', () => {});
    first.unsubscribe();

    const seen = [];
    manager.subscribe('history:abc', (data) => seen.push(data));
    const sub = fake.subs.get('history:abc');
    assert.equal(sub.subscribeCalls, 1);

    sub.emit('publication', { data: 'again' });
    assert.deepEqual(seen, ['again']);
  });

  it('publishes through the channel subscription when subscribed', async () => {
    const { fake, manager } = createManager();

    manager.subscribe('history:abc', () => {});
    await manager.publish('history:abc', { type: 'typing_started' });

    const sub = fake.subs.get('history:abc');
    assert.deepEqual(sub.published, [{ type: 'typing_started' }]);
    assert.deepEqual(fake.published, []);
  });

  it('publishes through the client without a subscription', async () => {
    const { fake, manager } = createManager();

    await manager.publish('history:abc', { type: 'typing_started' });
    assert.deepEqual(fake.published, [
      { channel: 'history:abc', data: { type: 'typing_started' } }
    ]);
  });

  it('propagates publish denials', async () => {
    const { fake, manager } = createManager();

    manager.subscribe('history:abc', () => {});
    fake.subs.get('history:abc').denyPublishes = true;

    let denied = false;
    await manager
      .publish('history:abc', { type: 'typing_started' })
      .catch(() => {
        denied = true;
      });
    assert.isTrue(denied);
  });
});

describe('SocketManager connection state', () => {
  it('is disconnected until something opens the connection', () => {
    const { manager, connections } = createManager();

    assert.equal(manager.getConnectionState(), ConnectionState.Disconnected);
    assert.equal(connections(), 0);
  });

  it('picks up the state the socket is already in', () => {
    const { manager } = createManager();

    // creating the client connects, so the first transition happens before we
    // can be listening for it
    manager.subscribe('history:abc', () => undefined);
    assert.equal(manager.getConnectionState(), ConnectionState.Connecting);
  });

  it('follows the connection', () => {
    const { fake, manager } = createManager();
    manager.subscribe('history:abc', () => undefined);

    const seen: ConnectionState[] = [];
    manager.onConnectionState((state) => seen.push(state));

    fake.transition('connected');
    fake.transition('disconnected');
    fake.transition('connecting');
    fake.transition('connected');

    assert.deepEqual(seen, [
      ConnectionState.Connected,
      ConnectionState.Disconnected,
      ConnectionState.Connecting,
      ConnectionState.Connected
    ]);
    assert.equal(manager.getConnectionState(), ConnectionState.Connected);
  });

  it('gives a new handler the current state without waiting for a change', async () => {
    const { fake, manager } = createManager();
    manager.subscribe('history:abc', () => undefined);
    fake.transition('connected');

    const seen: ConnectionState[] = [];
    manager.onConnectionState((state) => seen.push(state));

    await Promise.resolve();
    assert.deepEqual(seen, [ConnectionState.Connected]);
  });

  it('does not repeat a state it is already in', () => {
    const { fake, manager } = createManager();
    manager.subscribe('history:abc', () => undefined);
    fake.transition('connected');

    const seen: ConnectionState[] = [];
    manager.onConnectionState((state) => seen.push(state));

    fake.transition('connected');
    assert.deepEqual(seen, []);
  });

  it('does not repeat a state a same-tick transition already delivered', async () => {
    const { manager } = createManager();

    const seen: ConnectionState[] = [];
    // nothing has opened the connection yet, and then something does before
    // the initial delivery lands - that transition is the handler's first
    // word on where we are, so priming would only say it twice
    manager.onConnectionState((state) => seen.push(state));
    manager.subscribe('history:abc', () => undefined);

    await Promise.resolve();
    assert.deepEqual(seen, [ConnectionState.Connecting]);
  });

  it('stops telling a handler once it unsubscribes', () => {
    const { fake, manager } = createManager();
    manager.subscribe('history:abc', () => undefined);

    const seen: ConnectionState[] = [];
    const watch = manager.onConnectionState((state) => seen.push(state));
    fake.transition('connected');
    watch.unsubscribe();
    fake.transition('disconnected');

    assert.deepEqual(seen, [ConnectionState.Connected]);
  });
});

describe('SocketManager workspace changes', () => {
  const PAGE_WORKSPACE = '11111111-1111-4111-8111-111111111111';
  const OTHER_WORKSPACE = '22222222-2222-4222-8222-222222222222';

  let previousWorkspace: any;
  let reload: SinonStub;

  // being refused a subscription, as the server's subscribe proxy answers it
  const refuse = (fake: any, channel: string) => {
    fake.subs.get(channel).emit('error', {
      channel,
      type: 'subscribe',
      error: { code: 403, message: 'forbidden' }
    });
  };

  // what the session answers when asked which workspace it's in
  const sessionWorkspace = (uuid: string) => {
    mockGET(/\/api\/v2\/workspace\.json/, {}, { 'X-Temba-Workspace': uuid });
  };

  beforeEach(() => {
    previousWorkspace = (window as any).workspace;
    (window as any).workspace = { uuid: PAGE_WORKSPACE };
    resetWorkspaceStale();
    reload = stub(pageReloader, 'reload');
  });

  afterEach(() => {
    (window as any).workspace = previousWorkspace;
    resetWorkspaceStale();
    reload.restore();
    clearMockGets();
  });

  it('reloads when refused the workspace socket', async () => {
    const { fake, manager } = createManager();
    sessionWorkspace(OTHER_WORKSPACE);

    manager.subscribe(`org:${PAGE_WORKSPACE}`, () => undefined);
    refuse(fake, `org:${PAGE_WORKSPACE}`);
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(reload.callCount).to.equal(1);
  });

  it('reloads when refused the notifications socket', async () => {
    const { fake, manager } = createManager();
    sessionWorkspace(OTHER_WORKSPACE);
    const channel = `notifications:${PAGE_WORKSPACE}:user-uuid`;

    manager.subscribe(channel, () => undefined);
    refuse(fake, channel);
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(reload.callCount).to.equal(1);
  });

  it('ignores being refused any other socket', async () => {
    const { fake, manager } = createManager();
    // an agent opening a ticket outside their topics is refused the same way,
    // and their workspace is fine
    sessionWorkspace(OTHER_WORKSPACE);

    manager.subscribe('history:abc', () => undefined);
    refuse(fake, 'history:abc');
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(reload.callCount).to.equal(0);
  });

  it('stays put when the workspace is still ours', async () => {
    const { fake, manager } = createManager();
    // the socket can be refused for reasons of its own, so the session has
    // the last word on whether this page is showing the wrong workspace
    sessionWorkspace(PAGE_WORKSPACE);

    manager.subscribe(`org:${PAGE_WORKSPACE}`, () => undefined);
    refuse(fake, `org:${PAGE_WORKSPACE}`);
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(reload.callCount).to.equal(0);
  });

  it('ignores errors that are not a refusal', async () => {
    const { fake, manager } = createManager();
    sessionWorkspace(OTHER_WORKSPACE);

    manager.subscribe(`org:${PAGE_WORKSPACE}`, () => undefined);
    fake.subs.get(`org:${PAGE_WORKSPACE}`).emit('error', {
      channel: `org:${PAGE_WORKSPACE}`,
      type: 'subscribe',
      error: { code: 109, message: 'token expired' }
    });
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(reload.callCount).to.equal(0);
  });
});
