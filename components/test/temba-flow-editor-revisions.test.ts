import { html, fixture, expect } from '@open-wc/testing';
import { Editor } from '../src/flow/Editor';
import { IssuesWindow } from '../src/flow/IssuesWindow';
import { RevisionsWindow } from '../src/flow/RevisionsWindow';
import { stub, restore, SinonStub } from 'sinon';

customElements.define('temba-flow-editor-revisions', Editor);
if (!customElements.get('temba-issues-window')) {
  customElements.define('temba-issues-window', IssuesWindow);
}
if (!customElements.get('temba-revisions-window')) {
  customElements.define('temba-revisions-window', RevisionsWindow);
}

describe('Editor Revisions', () => {
  let element: Editor;
  let revisionsWindow: RevisionsWindow;
  let fetchStub: SinonStub;

  beforeEach(async () => {
    restore();
    fetchStub = stub(window, 'fetch');
    // Default any unstubbed fetches to an empty result so auto-refresh
    // triggered by store changes doesn't throw (each test that needs a
    // specific payload overrides via callsFake/resolves).
    fetchStub.callsFake(
      async () => new Response(JSON.stringify({ results: [] }), { status: 200 })
    );
    // Initialize without 'flow' attribute to prevent firstUpdated from calling getStore().getState()
    element = await fixture(
      html`<temba-flow-editor-revisions></temba-flow-editor-revisions>`
    );
    element.flow = 'test-flow';
    revisionsWindow = element.querySelector(
      'temba-revisions-window'
    ) as RevisionsWindow;
  });

  afterEach(() => {
    restore();
  });

  it('should include the current revision at the top of the list', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      {
        id: 3,
        created_on: '2023-01-03',
        user,
        changes: { tags: ['actions'] }
      },
      {
        id: 2,
        created_on: '2023-01-02',
        user,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2023-01-01',
        user,
        changes: { tags: ['metadata'] }
      }
    ];

    // Mock the fetch response for the revisions list
    const mockResponse = new Response(
      JSON.stringify({ results: mockRevisions }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }
    );

    fetchStub.resolves(mockResponse);

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(3);
    expect(revisions[0].id).to.equal(3);
    expect(revisions[1].id).to.equal(2);
    expect(revisions[2].id).to.equal(1);
  });

  it('should handle empty revisions list', async () => {
    const mockResponse = new Response(JSON.stringify({ results: [] }), {
      status: 200
    });
    fetchStub.resolves(mockResponse);

    await (revisionsWindow as any).fetchRevisions();
    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(0);
  });

  it('should handle single revision in list', async () => {
    const mockRevisions = [
      {
        id: 1,
        created_on: '2023-01-01',
        user: { id: 1, first_name: 'A', last_name: 'B', username: 'ab' }
      }
    ];
    const mockResponse = new Response(
      JSON.stringify({ results: mockRevisions }),
      { status: 200 }
    );
    fetchStub.resolves(mockResponse);

    await (revisionsWindow as any).fetchRevisions();
    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(1);
  });

  it('collapses revisions inside a 15 minute window onto the most recent and unions tags', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      {
        id: 4,
        created_on: '2024-06-01T12:30:00Z',
        user,
        changes: { tags: ['actions'] }
      },
      {
        id: 3,
        created_on: '2024-06-01T12:25:00Z',
        user,
        changes: { tags: ['layout'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:20:00Z',
        user,
        changes: { tags: ['actions', 'stickies'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T11:00:00Z',
        user,
        changes: { tags: ['metadata'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    // 4/3/2 are within 15 min of 4 → collapsed onto 4; 1 stands alone
    expect(revisions.length).to.equal(2);
    expect(revisions[0].id).to.equal(4);
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'layout',
      'stickies'
    ]);
    expect(revisions[1].id).to.equal(1);
    expect(revisions[1].changes.tags).to.deep.equal(['metadata']);
  });

  it('does not collapse revisions exactly 15 minutes apart', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      {
        id: 2,
        created_on: '2024-06-01T12:15:00Z',
        user,
        changes: { tags: ['actions'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:00:00Z',
        user,
        changes: { tags: ['actions'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(2);
    expect(revisions[0].id).to.equal(2);
    expect(revisions[1].id).to.equal(1);
  });

  it('groups revisions by author when only the email/name shape is sent', async () => {
    // The production API returns user: { email, name } (no username), so the
    // sameAuthor check has to recognize this shape — otherwise a single
    // editing session by one user lights up as a row per revision.
    const adam = { email: 'adam@example.com', name: 'Adam McAdmin' };
    const mockRevisions = [
      {
        id: 3,
        created_on: '2024-06-01T12:10:00Z',
        user: adam,
        changes: { tags: ['layout'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:09:00Z',
        user: adam,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:08:00Z',
        user: adam,
        changes: { tags: ['layout'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(3);
    expect(revisions[0].user.name).to.equal('Adam McAdmin');
  });

  it('breaks out into a new row when the next revision changes the author', async () => {
    const ann = { id: 1, first_name: 'A', last_name: 'A', username: 'ann' };
    const bob = { id: 2, first_name: 'B', last_name: 'B', username: 'bob' };
    const mockRevisions = [
      {
        id: 3,
        created_on: '2024-06-01T12:10:00Z',
        user: ann,
        changes: { tags: ['actions'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:05:00Z',
        user: bob,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:00:00Z',
        user: bob,
        changes: { tags: ['actions'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    // Ann's row stands alone; Bob's two revisions merge.
    expect(revisions.length).to.equal(2);
    expect(revisions[0].id).to.equal(3);
    expect(revisions[0].user.username).to.equal('ann');
    expect(revisions[1].id).to.equal(2);
    expect(revisions[1].user.username).to.equal('bob');
    expect(revisions[1].changes.tags.sort()).to.deep.equal([
      'actions',
      'layout'
    ]);
  });

  it('caps the merged label set at three and breaks out for a fourth', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      // Same window, all by the same author. Three distinct labels merge,
      // a fourth introduced by id 1 forces a break.
      {
        id: 4,
        created_on: '2024-06-01T12:10:00Z',
        user,
        changes: { tags: ['metadata'] }
      },
      {
        id: 3,
        created_on: '2024-06-01T12:08:00Z',
        user,
        changes: { tags: ['actions'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:06:00Z',
        user,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:04:00Z',
        user,
        changes: { tags: ['stickies'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(2);
    expect(revisions[0].id).to.equal(4);
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'layout',
      'metadata'
    ]);
    expect(revisions[1].id).to.equal(1);
    expect(revisions[1].changes.tags).to.deep.equal(['stickies']);
  });

  it('still merges revisions whose tags collapse to fewer than three labels', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    // Five raw localization tags, but they all collapse to one "translations"
    // label, so the cap doesn't trip.
    const mockRevisions = [
      {
        id: 5,
        created_on: '2024-06-01T12:10:00Z',
        user,
        changes: { tags: ['localization:spa'] }
      },
      {
        id: 4,
        created_on: '2024-06-01T12:09:00Z',
        user,
        changes: { tags: ['localization:fra'] }
      },
      {
        id: 3,
        created_on: '2024-06-01T12:08:00Z',
        user,
        changes: { tags: ['localization:deu'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:07:00Z',
        user,
        changes: { tags: ['localization:por'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:06:00Z',
        user,
        changes: { tags: ['localization:ita'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(5);
  });

  it('collapses a system spec-only revision into adjacent edits despite a different author', async () => {
    // The system bumps the spec version on its own behalf, which would
    // normally fragment a real user's run of edits because the author
    // differs. No-op revisions (empty tags or only "spec") should bypass
    // that author barrier so the row reflects the user's actual session.
    const adam = { email: 'adam@example.com', name: 'Adam McAdmin' };
    const system = { email: 'system', name: 'System' };
    const mockRevisions = [
      {
        id: 4,
        created_on: '2024-06-01T12:10:00Z',
        user: adam,
        changes: { tags: ['actions'] }
      },
      {
        id: 3,
        created_on: '2024-06-01T12:08:00Z',
        user: system,
        changes: { tags: ['spec'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:06:00Z',
        user: adam,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:04:00Z',
        user: system,
        changes: null
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(4);
    expect(revisions[0].user.email).to.equal('adam@example.com');
    // "spec" is stripped at the normalization boundary, so the merged tag
    // set only carries the real edits.
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'layout'
    ]);
  });

  it('absorbs a long chain of no-op revisions plus the next real change into one row', async () => {
    // System spec bumps land months or years apart and carry no editorial
    // intent. A chain of them should fold into a single row — and that row
    // must reach forward to swallow the first real edit too, otherwise we'd
    // present the user a revision where nothing actually changed.
    const system = { email: 'system', name: '' };
    const eric = { email: 'eric@textit.com', name: 'Gustavo Fring' };
    const mockRevisions = [
      {
        id: 1253,
        created_on: '2026-03-19T19:47:41Z',
        user: system,
        changes: { tags: [] }
      },
      {
        id: 1254,
        created_on: '2025-04-29T22:03:54Z',
        user: system,
        changes: { tags: [] }
      },
      {
        id: 1255,
        created_on: '2025-04-22T21:14:42Z',
        user: system,
        changes: { tags: ['spec'] }
      },
      {
        id: 1256,
        created_on: '2024-12-11T18:39:58Z',
        user: system,
        changes: { tags: [] }
      },
      {
        id: 1261,
        created_on: '2023-02-10T18:32:44Z',
        user: eric,
        changes: { tags: ['layout'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    // The id/created_on stay anchored to the newest revision so the row
    // sits at the correct point in time, but the displayed user is eric —
    // the system no-ops shouldn't claim authorship of his layout edit.
    expect(revisions[0].id).to.equal(1253);
    expect(revisions[0].created_on).to.equal('2026-03-19T19:47:41Z');
    expect(revisions[0].user.email).to.equal('eric@textit.com');
    expect(revisions[0].changes.tags).to.deep.equal(['layout']);
  });

  it('absorbs the first real change even when it would exceed the label cap on its own', async () => {
    // A sweeping edit can touch 4+ distinct label areas in a single
    // revision. If we enforced the label cap while a no-op-only chain
    // was reaching forward to grab its first real change, the merge
    // would fail and the no-op group would flush alone with no summary
    // — the empty-row case the absorb-forward rule exists to avoid.
    const system = { email: 'system', name: '' };
    const eric = { email: 'eric@textit.com', name: 'Eric' };
    const mockRevisions = [
      {
        id: 3,
        created_on: '2026-03-19T00:00:00Z',
        user: system,
        changes: { tags: [] }
      },
      {
        id: 2,
        created_on: '2025-01-01T00:00:00Z',
        user: system,
        changes: { tags: ['spec'] }
      },
      {
        id: 1,
        created_on: '2024-01-01T00:00:00Z',
        user: eric,
        changes: { tags: ['metadata', 'nodes', 'routing', 'actions'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(3);
    expect(revisions[0].user.email).to.equal('eric@textit.com');
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'metadata',
      'nodes',
      'routing'
    ]);
  });

  it('still folds in a trailing no-op even when the head already exceeds the label cap', async () => {
    // The very first rev of a group bypasses the cap, so a sweeping edit
    // can land as the head with `groupLabels.size > MAX_GROUP_LABELS`. A
    // no-op landing right behind it contributes zero labels and shouldn't
    // be stranded by a cap check that no longer makes sense.
    const eric = { email: 'eric@textit.com', name: 'Eric' };
    const system = { email: 'system', name: '' };
    const mockRevisions = [
      {
        id: 2,
        created_on: '2024-06-01T12:10:00Z',
        user: eric,
        changes: { tags: ['metadata', 'nodes', 'routing', 'actions'] }
      },
      {
        id: 1,
        created_on: '2024-06-01T12:08:00Z',
        user: system,
        changes: { tags: ['spec'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(2);
    expect(revisions[0].user.email).to.equal('eric@textit.com');
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'metadata',
      'nodes',
      'routing'
    ]);
  });

  it('stops absorbing after the first real change is pulled in', async () => {
    // Once a no-op chain has reached forward to grab a real edit, normal
    // barriers resume — a second far-away real edit should NOT be swept up.
    const system = { email: 'system', name: '' };
    const eric = { email: 'eric@textit.com', name: 'Eric' };
    const ann = { email: 'ann@example.com', name: 'Ann' };
    const mockRevisions = [
      {
        id: 4,
        created_on: '2026-03-19T00:00:00Z',
        user: system,
        changes: { tags: [] }
      },
      {
        id: 3,
        created_on: '2025-01-01T00:00:00Z',
        user: system,
        changes: { tags: ['spec'] }
      },
      {
        id: 2,
        created_on: '2024-01-01T00:00:00Z',
        user: eric,
        changes: { tags: ['layout'] }
      },
      {
        id: 1,
        created_on: '2023-01-01T00:00:00Z',
        user: ann,
        changes: { tags: ['actions'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(2);
    expect(revisions[0].id).to.equal(4);
    expect(revisions[0].changes.tags).to.deep.equal(['layout']);
    expect(revisions[1].id).to.equal(1);
    expect(revisions[1].changes.tags).to.deep.equal(['actions']);
  });

  it('does not count the "spec" tag toward the label cap when collapsing', async () => {
    // Three real labels plus a "spec" tag would naively look like four —
    // but spec is stripped at normalization, so the cap should still allow
    // these to merge into one row.
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      {
        id: 4,
        created_on: '2024-06-01T12:10:00Z',
        user,
        changes: { tags: ['metadata', 'spec'] }
      },
      {
        id: 3,
        created_on: '2024-06-01T12:08:00Z',
        user,
        changes: { tags: ['actions'] }
      },
      {
        id: 2,
        created_on: '2024-06-01T12:06:00Z',
        user,
        changes: { tags: ['layout'] }
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].changes.tags.sort()).to.deep.equal([
      'actions',
      'layout',
      'metadata'
    ]);
  });

  it('keeps the merged changes null when every revision in a window is null', async () => {
    const user = { id: 1, first_name: 'A', last_name: 'B', username: 'ab' };
    const mockRevisions = [
      {
        id: 2,
        created_on: '2024-06-01T12:05:00Z',
        user,
        changes: null
      },
      {
        id: 1,
        created_on: '2024-06-01T12:00:00Z',
        user,
        changes: null
      }
    ];

    fetchStub.resolves(
      new Response(JSON.stringify({ results: mockRevisions }), { status: 200 })
    );

    await (revisionsWindow as any).fetchRevisions();

    const revisions = (revisionsWindow as any).revisions;
    expect(revisions.length).to.equal(1);
    expect(revisions[0].id).to.equal(2);
    expect(revisions[0].changes).to.equal(null);
  });

  it('refresh() fetches the list when the window is open', async () => {
    fetchStub.callsFake(
      async () => new Response(JSON.stringify({ results: [] }), { status: 200 })
    );

    (revisionsWindow as any).hidden = false;
    await revisionsWindow.updateComplete;
    fetchStub.resetHistory();

    revisionsWindow.refresh();
    await revisionsWindow.updateComplete;

    expect(fetchStub.callCount).to.be.greaterThan(0);
  });

  it('refresh() is a no-op when the window is hidden', async () => {
    fetchStub.callsFake(
      async () => new Response(JSON.stringify({ results: [] }), { status: 200 })
    );

    fetchStub.resetHistory();
    revisionsWindow.refresh();
    await revisionsWindow.updateComplete;

    expect(fetchStub.callCount).to.equal(0);
  });

  it('should label the current revision and not show a revert button for it', async () => {
    (element as any).revisionsWindowHidden = false;
    await element.requestUpdate();

    const mockRevisions = [
      {
        id: 3,
        created_on: '2023-01-03',
        user: { id: 1, first_name: 'A', last_name: 'B', username: 'ab' }
      },
      {
        id: 2,
        created_on: '2023-01-02',
        user: { id: 1, first_name: 'A', last_name: 'B', username: 'ab' }
      }
    ];
    (revisionsWindow as any).revisions = mockRevisions;
    await revisionsWindow.updateComplete;

    const items = revisionsWindow.shadowRoot?.querySelectorAll(
      '.revision-item'
    ) as NodeListOf<HTMLElement>;
    expect(items.length).to.equal(2);

    // First item is the current revision
    expect(items[0].classList.contains('current')).to.be.true;
    expect(items[0].querySelector('.current-label')).to.exist;
    expect(items[0].querySelector('.revert-button')).to.not.exist;

    // Selecting the current revision should not show a revert button
    (revisionsWindow as any).viewingRevision = mockRevisions[0];
    await revisionsWindow.updateComplete;
    const refreshed = revisionsWindow.shadowRoot?.querySelectorAll(
      '.revision-item'
    ) as NodeListOf<HTMLElement>;
    expect(refreshed[0].classList.contains('selected')).to.be.true;
    expect(refreshed[0].querySelector('.revert-button')).to.not.exist;
    expect(refreshed[0].querySelector('.current-label')).to.exist;

    // Second item is not current and has no current label
    expect(items[1].classList.contains('current')).to.be.false;
    expect(items[1].querySelector('.current-label')).to.not.exist;
  });

  it('renders system-generated revisions with a "System update" label', async () => {
    (element as any).revisionsWindowHidden = false;
    await element.requestUpdate();

    const mockRevisions = [
      {
        id: 2,
        created_on: '2023-01-02',
        user: { email: 'adam@example.com', name: 'Adam' }
      },
      {
        id: 1,
        created_on: '2023-01-01',
        user: { email: 'system', name: '' }
      }
    ];
    (revisionsWindow as any).revisions = mockRevisions;
    await revisionsWindow.updateComplete;

    const items = revisionsWindow.shadowRoot?.querySelectorAll(
      '.revision-item'
    ) as NodeListOf<HTMLElement>;
    expect(items.length).to.equal(2);

    expect(items[0].textContent).to.contain('Adam');
    const systemMeta = items[1].querySelector('.revision-meta');
    expect(systemMeta?.querySelector('em')?.textContent).to.equal(
      'System update'
    );
  });

  it('should have purple color for revisions window and blue for selected item', async () => {
    // Force revisions window to show
    (element as any).revisionsWindowHidden = false;
    await element.requestUpdate();

    // Mock revisions so we can see list items
    const mockRevisions = [
      {
        id: 2,
        created_on: '2023-01-02',
        user: { id: 1, first_name: 'A', last_name: 'B', username: 'ab' }
      },
      {
        id: 1,
        created_on: '2023-01-01',
        user: { id: 1, first_name: 'A', last_name: 'B', username: 'ab' }
      }
    ];
    (revisionsWindow as any).revisions = mockRevisions;
    (revisionsWindow as any).viewingRevision = mockRevisions[1]; // Select a non-current revision

    await revisionsWindow.updateComplete;

    // Check revisions window color - now inside the component's shadow DOM
    const floatingWindow = revisionsWindow.shadowRoot?.querySelector(
      'temba-floating-window'
    );
    expect(floatingWindow).to.exist;
    expect(floatingWindow.getAttribute('color')).to.equal('rgb(142, 94, 167)');

    // Check selected item styles - inside the component's shadow DOM
    const selectedItem = revisionsWindow.shadowRoot?.querySelector(
      '.revision-item.selected'
    ) as HTMLElement;
    expect(selectedItem).to.exist;

    // We need to check inline styles because they are set in the template
    const style = selectedItem.getAttribute('style');
    expect(style).to.contain('#f0f6ff'); // Blue background
    expect(style).to.contain('#a4cafe'); // Blue border
  });
});
