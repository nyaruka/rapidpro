import { assert } from '@open-wc/testing';
import { generateUUID, generateUUIDv7 } from '../src/utils';

describe('UUID Generation', () => {
  it('generates a valid UUID v4 format', () => {
    const uuid = generateUUID();

    // Check that it's a string
    assert.isString(uuid);

    // Check UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    assert.match(uuid, uuidPattern, 'Should match UUID v4 format');

    // Check length
    assert.equal(uuid.length, 36);

    // Check that it contains hyphens in the right places
    assert.equal(uuid[8], '-');
    assert.equal(uuid[13], '-');
    assert.equal(uuid[18], '-');
    assert.equal(uuid[23], '-');
  });

  it('generates unique UUIDs', () => {
    const uuid1 = generateUUID();
    const uuid2 = generateUUID();
    const uuid3 = generateUUID();

    // All should be different
    assert.notEqual(uuid1, uuid2);
    assert.notEqual(uuid2, uuid3);
    assert.notEqual(uuid1, uuid3);
  });

  it('generates many unique UUIDs', () => {
    const uuids = new Set();
    const count = 1000;

    for (let i = 0; i < count; i++) {
      uuids.add(generateUUID());
    }

    // All should be unique
    assert.equal(uuids.size, count, 'All generated UUIDs should be unique');
  });

  it('generates a valid UUID v7 format', () => {
    const uuid = generateUUIDv7();

    // check that it's a string
    assert.isString(uuid);

    // check UUID v7 format: xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    assert.match(uuid, uuidPattern, 'Should match UUID v7 format');

    // check length
    assert.equal(uuid.length, 36);

    // check that it contains hyphens in the right places
    assert.equal(uuid[8], '-');
    assert.equal(uuid[13], '-');
    assert.equal(uuid[18], '-');
    assert.equal(uuid[23], '-');
  });

  it('generates unique UUIDs v7', () => {
    const uuid1 = generateUUIDv7();
    const uuid2 = generateUUIDv7();
    const uuid3 = generateUUIDv7();

    // all should be different
    assert.notEqual(uuid1, uuid2);
    assert.notEqual(uuid2, uuid3);
    assert.notEqual(uuid1, uuid3);
  });

  it('generates time-ordered UUIDs v7', () => {
    const uuid1 = generateUUIDv7();
    // small delay to ensure different timestamp
    const delayPromise = new Promise((resolve) => setTimeout(resolve, 5));
    return delayPromise.then(() => {
      const uuid2 = generateUUIDv7();

      // uuid v7 should be sortable by timestamp
      // the first uuid should come before the second when compared as strings
      assert.isTrue(
        uuid1 < uuid2,
        'Earlier UUID should be lexicographically smaller'
      );
    });
  });

  it('generates many unique UUIDs v7', () => {
    const uuids = new Set();
    const count = 1000;

    for (let i = 0; i < count; i++) {
      uuids.add(generateUUIDv7());
    }

    // all should be unique
    assert.equal(uuids.size, count, 'All generated UUIDs should be unique');
  });
});
