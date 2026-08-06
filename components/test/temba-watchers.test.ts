import { assert } from '@open-wc/testing';
import { stub } from 'sinon';
import { Watchers } from '../src/live/Watchers';

interface TestWatcher {
  name: string;
  onEvent: () => void;
}

const watcher = (name: string, onEvent: () => void = () => undefined) => ({
  name,
  onEvent
});

describe('Watchers', () => {
  let watchers: Watchers<TestWatcher>;

  beforeEach(() => {
    watchers = new Watchers<TestWatcher>('test watcher');
  });

  it('tracks membership', () => {
    const one = watcher('one');
    assert.equal(watchers.size, 0);
    assert.isFalse(watchers.has(one));

    watchers.add(one);
    assert.equal(watchers.size, 1);
    assert.isTrue(watchers.has(one));
    assert.isTrue(watchers.some((w) => w.name === 'one'));
  });

  it('reports whether a removal did anything', () => {
    const one = watcher('one');
    watchers.add(one);

    assert.isTrue(watchers.remove(one));
    // unsubscribing twice is a no-op, not a second teardown
    assert.isFalse(watchers.remove(one));
    assert.equal(watchers.size, 0);
  });

  it('hands out a snapshot rather than the list', () => {
    const one = watcher('one');
    watchers.add(one);

    const all = watchers.all();
    all.push(watcher('two'));
    assert.equal(watchers.size, 1);
  });

  it('delivers to everyone registered', () => {
    const seen: string[] = [];
    watchers.add(watcher('one'));
    watchers.add(watcher('two'));

    watchers.each((w) => seen.push(w.name));
    assert.deepEqual(seen, ['one', 'two']);
  });

  it('delivers only to those matching', () => {
    const seen: string[] = [];
    watchers.add(watcher('one'));
    watchers.add(watcher('two'));

    watchers.each(
      (w) => seen.push(w.name),
      (w) => w.name === 'two'
    );
    assert.deepEqual(seen, ['two']);
  });

  it('keeps one subscriber throwing from costing the others', () => {
    const consoleStub = stub(console, 'error');
    const seen: string[] = [];
    watchers.add(watcher('one'));
    watchers.add(watcher('boom'));
    watchers.add(watcher('three'));

    watchers.each((w) => {
      if (w.name === 'boom') {
        throw new Error('boom');
      }
      seen.push(w.name);
    });

    assert.deepEqual(seen, ['one', 'three']);
    assert.isTrue(consoleStub.calledWith('test watcher failed'));
    consoleStub.restore();
  });

  it('survives a subscriber leaving mid delivery', () => {
    const seen: string[] = [];
    const one = watcher('one');
    const two = watcher('two');
    watchers.add(one);
    watchers.add(two);

    watchers.each((w) => {
      seen.push(w.name);
      if (w.name === 'one') {
        // a delivery that tears its neighbour down would otherwise shift the
        // list out from under the loop
        watchers.remove(two);
      }
    });

    assert.deepEqual(seen, ['one', 'two']);
  });

  describe('prime', () => {
    it('delivers off the current task', async () => {
      const seen: string[] = [];
      const one = watcher('one');
      watchers.add(one);

      watchers.prime(one, (w) => seen.push(w.name));
      assert.deepEqual(seen, [], 'should not have delivered synchronously');

      await Promise.resolve();
      assert.deepEqual(seen, ['one']);
    });

    it('skips a subscriber that left before it landed', async () => {
      const seen: string[] = [];
      const one = watcher('one');
      watchers.add(one);

      watchers.prime(one, (w) => seen.push(w.name));
      watchers.remove(one);

      await Promise.resolve();
      assert.deepEqual(seen, []);
    });
  });

  it('clears everyone', () => {
    watchers.add(watcher('one'));
    watchers.add(watcher('two'));

    watchers.clear();
    assert.equal(watchers.size, 0);
  });
});
