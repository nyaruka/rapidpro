import { expect } from '@open-wc/testing';
import {
  isNoOpChanges,
  normalizeChanges,
  summarizeChanges
} from '../src/flow/revision-summary';

describe('summarizeChanges', () => {
  it('returns empty string for null/undefined/empty tags', () => {
    expect(summarizeChanges(null)).to.equal('');
    expect(summarizeChanges(undefined)).to.equal('');
    expect(summarizeChanges({ tags: [] })).to.equal('');
  });

  it('renders a single tag verb-first', () => {
    expect(summarizeChanges({ tags: ['actions'] })).to.equal('Changed actions');
    expect(summarizeChanges({ tags: ['metadata'] })).to.equal(
      'Changed metadata'
    );
  });

  it('joins two tags with "and"', () => {
    expect(summarizeChanges({ tags: ['actions', 'layout'] })).to.equal(
      'Changed actions and layout'
    );
  });

  it('orders tags by category priority regardless of input order', () => {
    expect(summarizeChanges({ tags: ['layout', 'metadata'] })).to.equal(
      'Changed metadata and layout'
    );
    expect(
      summarizeChanges({ tags: ['stickies', 'nodes', 'metadata'] })
    ).to.equal('Changed metadata, nodes, and stickies');
  });

  it('lists all tags with an Oxford comma when there are 3+', () => {
    expect(
      summarizeChanges({ tags: ['metadata', 'actions', 'layout'] })
    ).to.equal('Changed metadata, actions, and layout');
    expect(
      summarizeChanges({
        tags: ['layout', 'stickies', 'metadata', 'actions', 'nodes']
      })
    ).to.equal('Changed metadata, nodes, actions, stickies, and layout');
  });

  it('collapses multiple localization:<lang> tags into a single "translations" label', () => {
    expect(
      summarizeChanges({ tags: ['localization:spa', 'localization:fra'] })
    ).to.equal('Changed translations');
  });

  it('treats a localization tag as one label alongside other tags', () => {
    expect(
      summarizeChanges({
        tags: ['actions', 'localization:spa', 'localization:fra']
      })
    ).to.equal('Changed actions and translations');
  });

  it('ignores unknown tags', () => {
    expect(summarizeChanges({ tags: ['actions', 'something_new'] })).to.equal(
      'Changed actions'
    );
    // an entirely unknown set yields nothing
    expect(summarizeChanges({ tags: ['something_new'] })).to.equal('');
  });

  it('never surfaces the "spec" tag in a summary', () => {
    expect(summarizeChanges({ tags: ['spec'] })).to.equal('');
    expect(summarizeChanges({ tags: ['spec', 'actions'] })).to.equal(
      'Changed actions'
    );
  });
});

describe('normalizeChanges', () => {
  it('returns null for null/undefined/empty inputs', () => {
    expect(normalizeChanges(null)).to.equal(null);
    expect(normalizeChanges(undefined)).to.equal(null);
    expect(normalizeChanges({ tags: [] })).to.equal(null);
  });

  it('strips the "spec" housekeeping tag', () => {
    expect(normalizeChanges({ tags: ['spec'] })).to.equal(null);
    expect(normalizeChanges({ tags: ['spec', 'actions'] })).to.deep.equal({
      tags: ['actions']
    });
  });

  it('leaves real tags untouched', () => {
    expect(normalizeChanges({ tags: ['actions', 'layout'] })).to.deep.equal({
      tags: ['actions', 'layout']
    });
  });
});

describe('isNoOpChanges', () => {
  it('treats null/undefined and empty tag lists as no-ops', () => {
    expect(isNoOpChanges(null)).to.equal(true);
    expect(isNoOpChanges(undefined)).to.equal(true);
    expect(isNoOpChanges({ tags: [] })).to.equal(true);
  });

  it('treats spec-only tag lists as no-ops', () => {
    expect(isNoOpChanges({ tags: ['spec'] })).to.equal(true);
    expect(isNoOpChanges({ tags: ['spec', 'spec'] })).to.equal(true);
  });

  it('treats anything beyond "spec" as a real change', () => {
    expect(isNoOpChanges({ tags: ['spec', 'actions'] })).to.equal(false);
    expect(isNoOpChanges({ tags: ['actions'] })).to.equal(false);
    expect(isNoOpChanges({ tags: ['localization:spa'] })).to.equal(false);
  });
});
