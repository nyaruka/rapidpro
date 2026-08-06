import '../temba-modules';
import { expect } from '@open-wc/testing';
import { DateTime, Duration } from 'luxon';
import { Store } from '../src/store/Store';
import { loadStore, mockGET, clearMockGets } from './utils.test';

// a dirty-trackable stand-in for a component registered with the store
const trackable = (dirtyMessage?: string) => {
  const element: any = {
    dirty: true,
    dirtyMessage,
    cleaned: 0,
    markClean() {
      element.cleaned++;
      element.dirty = false;
    }
  };
  return element;
};

describe('temba-store api', () => {
  let store: Store;

  beforeEach(async () => {
    store = await loadStore();
  });

  afterEach(() => {
    clearMockGets();
  });

  describe('dirty tracking', () => {
    it('reports no message when nothing is dirty', () => {
      expect(store.getDirtyMessage()).to.equal(undefined);
    });

    it('reports a default message for a dirty element', () => {
      store.markDirty(trackable());
      expect(store.getDirtyMessage()).to.contain('unsaved changes');
    });

    it('prefers the element supplied message', () => {
      store.markDirty(trackable('Your draft will be lost'));
      expect(store.getDirtyMessage()).to.equal('Your draft will be lost');
    });

    it('reports the message of the first dirty element', () => {
      store.markDirty(trackable('First'));
      store.markDirty(trackable('Second'));
      expect(store.getDirtyMessage()).to.equal('First');
    });

    it('registers an element only once', () => {
      const element = trackable();
      store.markDirty(element);
      store.markDirty(element);
      store.cleanAll();
      expect(element.cleaned).to.equal(1);
    });

    it('cleans every registered element', () => {
      const first = trackable();
      const second = trackable();
      store.markDirty(first);
      store.markDirty(second);

      store.cleanAll();

      expect(first.cleaned).to.equal(1);
      expect(second.cleaned).to.equal(1);
      expect(store.getDirtyMessage()).to.equal(undefined);
    });

    it('forgets an element that marks itself clean', () => {
      const element = trackable();
      store.markDirty(element);
      store.markClean(element);
      expect(store.getDirtyMessage()).to.equal(undefined);
    });
  });

  describe('shiftAndRound', () => {
    const duration = (opts: any) => Duration.fromObject(opts);

    it('uses the singular form for exactly one unit', () => {
      expect(
        store.shiftAndRound(duration({ days: 1 }), 'days', 'day')
      ).to.equal('1 day');
      expect(
        store.shiftAndRound(duration({ hours: 1 }), 'hours', 'hour')
      ).to.equal('1 hour');
    });

    it('uses the plural form otherwise', () => {
      expect(
        store.shiftAndRound(duration({ days: 3 }), 'days', 'day')
      ).to.equal('3 days');
    });

    it('rounds to the nearest whole unit', () => {
      expect(
        store.shiftAndRound(
          duration({ hours: 2, minutes: 40 }),
          'hours',
          'hour'
        )
      ).to.equal('3 hours');
      expect(
        store.shiftAndRound(
          duration({ hours: 1, minutes: 10 }),
          'hours',
          'hour'
        )
      ).to.equal('1 hour');
    });
  });

  describe('getCountdown', () => {
    const inFuture = (opts: any) => DateTime.now().plus(opts);

    it('collapses anything past a month', () => {
      expect(store.getCountdown(inFuture({ months: 3 }))).to.equal('> 1 month');
    });

    it('counts down in days', () => {
      expect(store.getCountdown(inFuture({ days: 5, hours: 1 }))).to.equal(
        '~ 5 days'
      );
    });

    it('counts down in hours', () => {
      expect(store.getCountdown(inFuture({ hours: 5 }))).to.equal('~ 5 hours');
    });

    it('counts down in minutes', () => {
      expect(store.getCountdown(inFuture({ minutes: 30 }))).to.equal(
        '~ 30 minutes'
      );
    });

    it('uses the singular form for a single hour', () => {
      expect(store.getCountdown(inFuture({ hours: 1, minutes: 2 }))).to.equal(
        '~ 1 hour'
      );
    });
  });

  describe('keyed assets', () => {
    it('stores values under a name', () => {
      store.setKeyedAssets('custom', ['one', 'two']);
      expect(store.getKeyedAssets()['custom']).to.deep.equal(['one', 'two']);
    });

    it('replaces any previous values', () => {
      store.setKeyedAssets('custom', ['one']);
      store.setKeyedAssets('custom', ['two']);
      expect(store.getKeyedAssets()['custom']).to.deep.equal(['two']);
    });
  });

  describe('shortcuts', () => {
    it('returns an empty list before anything is loaded', () => {
      (store as any).shortcuts = null;
      expect(store.getShortcuts()).to.deep.equal([]);
    });

    it('returns the loaded shortcuts', () => {
      const shortcuts = [
        { uuid: 'a', name: 'Greeting', text: 'Hi', modified_on: '' }
      ];
      (store as any).shortcuts = shortcuts;
      expect(store.getShortcuts()).to.equal(shortcuts);
    });

    it('refreshes shortcuts from the endpoint', async () => {
      mockGET(/shortcuts\.json/, {
        results: [
          { uuid: 'a', name: 'Greeting', text: 'Hi', modified_on: '' },
          { uuid: 'b', name: 'Bye', text: 'Later', modified_on: '' }
        ],
        next: null
      });
      (store as any).shortcutsEndpoint = '/api/v2/shortcuts.json';

      await store.refreshShortcuts();

      expect(store.getShortcuts()).to.have.length(2);
      expect(store.getShortcuts()[0].name).to.equal('Greeting');
    });
  });

  describe('refreshGlobals', () => {
    it('records the keys of every global', async () => {
      mockGET(/globals\.json/, {
        results: [{ key: 'org_name' }, { key: 'support_email' }],
        next: null
      });
      (store as any).globalsEndpoint = '/api/v2/globals.json';

      await store.refreshGlobals();

      expect(store.getKeyedAssets()['globals']).to.deep.equal([
        'org_name',
        'support_email'
      ]);
    });
  });

  describe('getResults', () => {
    const RESULTS_URL = '/api/v2/things.json';

    it('fetches and caches results', async () => {
      mockGET(/things\.json/, { results: [{ id: 1 }], next: null });
      const first = await store.getResults(RESULTS_URL);
      expect(first).to.deep.equal([{ id: 1 }]);

      // a second call is served from cache, so changing the mock has no effect
      clearMockGets();
      mockGET(/things\.json/, { results: [{ id: 2 }], next: null });
      const second = await store.getResults(RESULTS_URL);
      expect(second).to.deep.equal([{ id: 1 }]);
    });

    it('refetches when forced', async () => {
      mockGET(/things\.json/, { results: [{ id: 1 }], next: null });
      await store.getResults(RESULTS_URL);

      clearMockGets();
      mockGET(/things\.json/, { results: [{ id: 2 }], next: null });
      const forced = await store.getResults(RESULTS_URL, { force: true });
      expect(forced).to.deep.equal([{ id: 2 }]);
    });

    it('shares one fetch between concurrent callers', async () => {
      mockGET(/things\.json/, { results: [{ id: 1 }], next: null });
      const [a, b, c] = await Promise.all([
        store.getResults(RESULTS_URL),
        store.getResults(RESULTS_URL),
        store.getResults(RESULTS_URL)
      ]);
      expect(a).to.deep.equal([{ id: 1 }]);
      expect(b).to.deep.equal(a);
      expect(c).to.deep.equal(a);
    });
  });

  describe('cache', () => {
    const cached = (url: string) => (store as any).cache.get(url);

    it('removes an entry', () => {
      store.updateCache('/some/url', { hello: 'world' });
      expect(cached('/some/url')).to.deep.equal({ hello: 'world' });
      store.removeFromCache('/some/url');
      expect(cached('/some/url')).to.equal(undefined);
    });

    it('ignores removal of an unknown entry', () => {
      // no throw is the assertion here
      store.removeFromCache('/never/cached');
    });

    it('fires an update event when the cache is written', () => {
      const seen: any[] = [];
      store.addEventListener('temba-store-updated', (e: any) =>
        seen.push(e.detail)
      );
      store.updateCache('/some/url', { hello: 'world' });
      expect(seen).to.have.length(1);
      expect(seen[0].url).to.equal('/some/url');
    });
  });

  describe('user avatars', () => {
    it('stores and reads an avatar', () => {
      store.setUserAvatar('user-1', 'http://example.com/a.png');
      expect(store.getUserAvatar('user-1')).to.equal(
        'http://example.com/a.png'
      );
    });

    it('ignores incomplete entries', () => {
      store.setUserAvatar('', 'http://example.com/a.png');
      store.setUserAvatar('user-2', '');
      expect(store.getUserAvatar('user-2')).to.equal(undefined);
    });
  });

  describe('resolveUsers', () => {
    it('fills in avatars for referenced users', async () => {
      mockGET(/users\.json\?uuid=user-1/, {
        results: [
          {
            uuid: 'user-1',
            email: 'ann@example.com',
            first_name: 'Ann',
            last_name: 'Smith',
            avatar: 'http://example.com/ann.png'
          }
        ],
        next: null
      });

      const items = [
        { created_by: { email: 'ann@example.com', uuid: 'user-1' } }
      ];
      await store.resolveUsers(items, ['created_by']);

      expect(items[0].created_by).to.include({
        avatar: 'http://example.com/ann.png',
        uuid: 'user-1'
      });
      expect(store.getUserAvatar('user-1')).to.equal(
        'http://example.com/ann.png'
      );
    });

    it('resolves users at a nested path', async () => {
      mockGET(/users\.json\?uuid=user-2/, {
        results: [
          {
            uuid: 'user-2',
            email: 'bo@example.com',
            first_name: 'Bo',
            avatar: 'http://example.com/bo.png'
          }
        ],
        next: null
      });

      const items = [
        { ticket: { assignee: { email: 'bo@example.com', uuid: 'user-2' } } }
      ];
      await store.resolveUsers(items, ['ticket.assignee']);

      expect((items[0].ticket.assignee as any).avatar).to.equal(
        'http://example.com/bo.png'
      );
    });

    it('ignores items missing the referenced key', async () => {
      const items = [{ other: 'value' }];
      // resolves without attempting any fetch
      await store.resolveUsers(items, ['created_by']);
      expect(items[0]).to.deep.equal({ other: 'value' });
    });

    it('handles an empty item list', async () => {
      await store.resolveUsers([], ['created_by']);
    });
  });
});
