import { assert, expect } from '@open-wc/testing';
import { SinonStub, stub } from 'sinon';
import { CustomEventType } from '../src/interfaces';
import {
  annotateTree,
  ArticleList,
  ArticleRow,
  INDENT,
  moveSubtree,
  toOrder,
  visibleRows
} from '../src/list/ArticleList';
import {
  assertScreenshot,
  clearMockGets,
  clearMockPosts,
  getClip,
  getComponent,
  loadStore,
  mockGET,
  mockPOST,
  waitForCondition
} from './utils.test';

const TAG = 'temba-article-list';

const ENDPOINT = '/api/internal/articles.json';
const SORT_URL = '/article/sort/';
const PUBLISH_URL = '/article/publish/';

// getting-started
//   installing (draft)
//   configuring
// flows
//   nodes
//     rules (draft)
const ARTICLES = [
  {
    uuid: 'getting-started',
    title: 'Getting Started',
    status: 'published',
    parent: null,
    depth: 0,
    modified_on: '2026-01-01T00:00:00Z'
  },
  {
    uuid: 'installing',
    title: 'Installing',
    status: 'draft',
    parent: 'getting-started',
    depth: 1,
    modified_on: '2026-01-02T00:00:00Z'
  },
  {
    uuid: 'configuring',
    title: 'Configuring',
    status: 'published',
    parent: 'getting-started',
    depth: 1,
    modified_on: '2026-01-03T00:00:00Z'
  },
  {
    uuid: 'flows',
    title: 'Flows',
    status: 'published',
    parent: null,
    depth: 0,
    modified_on: '2026-01-04T00:00:00Z'
  },
  {
    uuid: 'nodes',
    title: 'Nodes',
    status: 'published',
    parent: 'flows',
    depth: 1,
    modified_on: '2026-01-05T00:00:00Z'
  },
  {
    uuid: 'rules',
    title: 'Rules',
    status: 'draft',
    parent: 'nodes',
    depth: 2,
    modified_on: '2026-01-06T00:00:00Z'
  }
];

// a tree as the component holds it, written as (uuid, depth) pairs so the
// shape of a case is readable at a glance
const tree = (...rows: [string, number][]): ArticleRow[] =>
  annotateTree(
    rows.map(([uuid, depth]) => ({
      uuid,
      title: uuid,
      status: 'published',
      parent: null,
      depth,
      modified_on: ''
    }))
  );

const shape = (rows: ArticleRow[]): [string, number][] =>
  rows.map((row) => [row.uuid, row.depth]);

const getList = async (attrs: any = {}, width = 800) => {
  const list = (await getComponent(
    TAG,
    { endpoint: ENDPOINT, 'sort-endpoint': SORT_URL, ...attrs },
    '',
    width
  )) as ArticleList;
  await waitForCondition(() => (list as any).items.length > 0);
  await list.updateComplete;
  return list;
};

const getRows = (list: ArticleList): HTMLElement[] =>
  Array.from(list.shadowRoot.querySelectorAll('tr.row'));

const getTitles = (list: ArticleList): string[] =>
  getRows(list).map((row) => row.querySelector('.title').textContent.trim());

// the fetch stub's call history spans the whole run, so each test tracks
// a baseline and only looks at its own posts
let postBaseline = 0;
let publishBaseline = 0;

const allPostsTo = (url: string): any[] =>
  (window.fetch as SinonStub)
    .getCalls()
    .filter(
      (call) =>
        String(call.args[0]).includes(url) && call.args[1]?.method === 'POST'
    )
    .map((call) => JSON.parse(call.args[1].body));

const allSortPosts = (): any[] => allPostsTo(SORT_URL);

const getSortPosts = (): any[] => allSortPosts().slice(postBaseline);

const getPublishPosts = (): any[] =>
  allPostsTo(PUBLISH_URL).slice(publishBaseline);

/** Drags a row by its handle to a point, in the same way a user would. */
const dragRow = async (
  list: ArticleList,
  uuid: string,
  toX: number,
  toY: number
) => {
  const row = getRows(list).find(
    (candidate) => candidate.querySelector('.title').textContent.trim() === uuid
  );
  const handle = row.querySelector('.drag-handle');
  const bounds = handle.getBoundingClientRect();

  await moveMouse(
    bounds.left + bounds.width / 2,
    bounds.top + bounds.height / 2
  );
  await mouseDown();
  await moveMouse(toX, toY);
  await mouseUp();
  await list.updateComplete;
};

describe(TAG, () => {
  beforeEach(async () => {
    clearMockGets();
    clearMockPosts();
    mockGET(/\/api\/internal\/articles\.json/, { results: ARTICLES });
    mockPOST(/\/article\/sort\//, { status: 'ok' });
    mockPOST(/\/article\/publish\//, { status: 'ok' });
    postBaseline = allSortPosts().length;
    publishBaseline = allPostsTo(PUBLISH_URL).length;
  });

  it('can be created with article columns', async () => {
    const list = await getList();

    assert.instanceOf(list, ArticleList);

    // the drag and publish columns are only offered when there's somewhere to post them to
    expect(list.columns.map((column) => column.key)).to.deep.equal([
      'drag',
      'title',
      'status',
      'modified_on'
    ]);

    // the tree is the order, so there's nothing to search or sort by
    expect(list.searchable).to.be.false;
    expect(list.columns.some((column) => column.sortable)).to.be.false;
  });

  it('drops the drag column without permission to reorder', async () => {
    const list = await getList({ 'sort-endpoint': '' });

    expect(list.columns.map((column) => column.key)).to.deep.equal([
      'title',
      'status',
      'modified_on'
    ]);
    expect(list.shadowRoot.querySelector('.drag-handle')).to.not.exist;
  });

  it('ends a row with a publish switch when permitted', async () => {
    const list = await getList({ 'publish-endpoint': PUBLISH_URL });

    // the switch says what the status is as well as setting it, so the pill that only said it steps aside
    expect(list.columns.map((column) => column.key)).to.deep.equal([
      'drag',
      'title',
      'modified_on',
      'publish'
    ]);
    expect(list.shadowRoot.querySelector('.status-pill')).to.not.exist;

    const switches = Array.from(
      list.shadowRoot.querySelectorAll('temba-toggle')
    ) as any[];
    expect(switches).to.have.length(6);

    // each says whether its own article is published
    expect(switches.map((toggle) => toggle.checked)).to.deep.equal([
      true,
      false,
      true,
      true,
      true,
      false
    ]);
  });

  it('nests rows by depth with rails and disclosure chevrons', async () => {
    const list = await getList();

    expect(getTitles(list)).to.deep.equal([
      'Getting Started',
      'Installing',
      'Configuring',
      'Flows',
      'Nodes',
      'Rules'
    ]);

    const cells = Array.from(
      list.shadowRoot.querySelectorAll('.tree-cell')
    ) as HTMLElement[];

    // each level of nesting is a fixed indent, and carries a guide rail
    // for every level above it
    expect(cells.map((cell) => cell.style.paddingLeft)).to.deep.equal([
      '0px',
      `${INDENT}px`,
      `${INDENT}px`,
      '0px',
      `${INDENT}px`,
      `${INDENT * 2}px`
    ]);
    expect(
      cells.map((cell) => cell.querySelectorAll('.rail').length)
    ).to.deep.equal([0, 1, 1, 0, 1, 2]);

    // only an article with children gets a chevron, and only it reads as
    // a heading for the rows under it
    const chevrons = cells.map(
      (cell) => !!cell.querySelector('.disclosure temba-icon')
    );
    expect(chevrons).to.deep.equal([true, false, false, true, true, false]);
    expect(
      cells.map((cell) => !!cell.querySelector('.title.branch'))
    ).to.deep.equal([true, false, false, true, true, false]);
  });

  it('shows a draft badge and the last modified date', async () => {
    const list = await getList();
    const rows = getRows(list);

    expect(rows[0].querySelector('.status-pill')).to.not.exist;
    expect(rows[1].querySelector('.status-pill').textContent.trim()).to.equal(
      'Draft'
    );
    expect(
      rows[1].querySelector('.status-pill').classList.contains('status-neutral')
    ).to.be.true;
    expect(rows[1].querySelector('temba-date').getAttribute('value')).to.equal(
      '2026-01-02T00:00:00Z'
    );
  });

  it('folds a branch away when its chevron is clicked', async () => {
    // the test browser forces prefers-reduced-motion, so this is also the reduced motion path: the fold's result
    // with none of its travel
    const list = await getList();

    const chevron = list.shadowRoot.querySelector('.disclosure') as HTMLElement;
    chevron.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await list.updateComplete;

    expect(getTitles(list)).to.deep.equal([
      'Getting Started',
      'Flows',
      'Nodes',
      'Rules'
    ]);
    expect(list.shadowRoot.querySelector('tr.row.leaving')).to.not.exist;

    // folding a branch isn't opening the article
    expect(getSortPosts()).to.be.empty;

    chevron.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await list.updateComplete;

    expect(getTitles(list)).to.have.length(6);
    expect(list.shadowRoot.querySelector('tr.row.entering')).to.not.exist;
  });

  it('plays the fold for a viewer who is fine with motion', async () => {
    const list = await getList();

    // the test browser forces reduced motion, so motion has to be asked for
    const media = stub(window, 'matchMedia').returns({
      matches: false
    } as MediaQueryList);

    try {
      const chevron = list.shadowRoot.querySelector(
        '.disclosure'
      ) as HTMLElement;
      chevron.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await list.updateComplete;

      // the branch folds shut in place before it leaves the list
      const leaving = getRows(list).filter((row) =>
        row.classList.contains('leaving')
      );
      expect(
        leaving.map((row) => row.querySelector('.title').textContent.trim())
      ).to.deep.equal(['Installing', 'Configuring']);
      expect(getTitles(list)).to.have.length(6);

      // the block folds shut as a unit - each row plays its own slice
      // of the fold, bottom row first, like a container clipping shut
      expect(leaving.map((row) => row.getAttribute('style'))).to.deep.equal([
        '--fold-delay: 100ms; --fold-duration: 100ms',
        '--fold-delay: 0ms; --fold-duration: 100ms'
      ]);

      await waitForCondition(() => getTitles(list).length === 4);

      chevron.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await list.updateComplete;

      // the rows are back straight away, playing the fold open top
      // row first - the same sweep as closing, run in reverse
      const entering = getRows(list).filter((row) =>
        row.classList.contains('entering')
      );
      expect(entering).to.have.length(2);
      expect(entering.map((row) => row.getAttribute('style'))).to.deep.equal([
        '--fold-delay: 0ms; --fold-duration: 100ms',
        '--fold-delay: 100ms; --fold-duration: 100ms'
      ]);

      // and once the fold lands they are ordinary rows again
      await waitForCondition(
        () => !list.shadowRoot.querySelector('tr.row.entering')
      );
    } finally {
      media.restore();
    }

    // the fold itself is css, guarded for viewers who asked for less motion
    const styles = ArticleList.styles.cssText;
    expect(styles).to.contain('fold-open');
    expect(styles).to.contain('fold-shut');
    expect(styles).to.contain('prefers-reduced-motion');
  });

  it('asks the host to open an article rather than navigating to one', async () => {
    const list = await getList();

    const clicked: string[] = [];
    const redirects: string[] = [];
    list.addEventListener(CustomEventType.RowClick, (event: any) =>
      clicked.push(event.detail.item.uuid)
    );
    list.addEventListener(CustomEventType.Redirected, (event: any) =>
      redirects.push(event.detail.url)
    );

    getRows(list)[3].dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await list.updateComplete;

    // an article is read and written in a dialog over the list, so there's no page to link a row to - not even one
    // a ctrl-click could open in a tab
    expect(clicked).to.deep.equal(['flows']);
    expect(redirects).to.be.empty;
    expect((list as any).getRowHref()).to.be.null;

    // and the rows still read as clickable, since clicking one does lead somewhere
    expect(getRows(list).every((row) => row.classList.contains('clickable'))).to
      .be.true;
  });

  it('publishes an article from its row without opening it', async () => {
    const list = await getList({ 'publish-endpoint': PUBLISH_URL });

    const clicked: string[] = [];
    list.addEventListener(CustomEventType.RowClick, (event: any) =>
      clicked.push(event.detail.item.uuid)
    );

    // Installing is the draft, so its switch is the one to turn on
    const toggle = list.shadowRoot.querySelectorAll('temba-toggle')[1] as any;
    toggle.click();
    await list.updateComplete;

    expect(getPublishPosts()).to.deep.equal([
      { uuid: 'installing', status: 'published' }
    ]);

    // shown straight away rather than waiting for the tree to come back
    expect((list as any).items[1].status).to.equal('published');

    // and using the switch isn't opening the article it belongs to
    expect(clicked).to.be.empty;

    // turning one off says so the same way
    const published = list.shadowRoot.querySelectorAll(
      'temba-toggle'
    )[0] as any;
    published.click();
    await list.updateComplete;

    expect(getPublishPosts()[1]).to.deep.equal({
      uuid: 'getting-started',
      status: 'draft'
    });
  });

  it('reorders siblings by dragging', async () => {
    const list = await getList();
    const rows = getRows(list);

    // drag Flows up above Getting Started, staying at the same level
    const target = rows[0].getBoundingClientRect();
    await dragRow(list, 'Flows', target.left + 40, target.top + 2);

    expect(getTitles(list).slice(0, 3)).to.deep.equal([
      'Flows',
      'Nodes',
      'Rules'
    ]);

    // a parent takes its subtree with it, and the whole resulting order is
    // posted for the server to re-derive the tree from
    const posted = getSortPosts();
    expect(posted).to.have.length(1);
    expect(posted[0]).to.deep.equal([
      { uuid: 'flows', parent: null, sort_order: 0 },
      { uuid: 'nodes', parent: 'flows', sort_order: 1 },
      { uuid: 'rules', parent: 'nodes', sort_order: 2 },
      { uuid: 'getting-started', parent: null, sort_order: 3 },
      { uuid: 'installing', parent: 'getting-started', sort_order: 4 },
      { uuid: 'configuring', parent: 'getting-started', sort_order: 5 }
    ]);
  });

  it('reparents by dragging sideways', async () => {
    const list = await getList();
    const rows = getRows(list);

    // Configuring is dragged right where it stands, which makes it a
    // child of its own former sibling
    const box = rows[2].getBoundingClientRect();
    await dragRow(list, 'Configuring', box.left + 200, box.top + 2);

    const posted = getSortPosts();
    expect(posted).to.have.length(1);
    expect(posted[0].slice(0, 3)).to.deep.equal([
      { uuid: 'getting-started', parent: null, sort_order: 0 },
      { uuid: 'installing', parent: 'getting-started', sort_order: 1 },
      { uuid: 'configuring', parent: 'installing', sort_order: 2 }
    ]);
  });

  it('renders the article tree (screenshot)', async () => {
    // the modified dates need a store to know the workspace's locale
    await loadStore();
    const list = await getList({ 'publish-endpoint': PUBLISH_URL });
    await assertScreenshot('article-list/list', getClip(list));
  });
});

describe('article tree', () => {
  it('measures each row against its own subtree', () => {
    const rows = tree(['a', 0], ['b', 1], ['c', 2], ['d', 0]);

    expect(rows.map((row) => row.height)).to.deep.equal([2, 1, 0, 0]);
  });

  it('hides the descendants of a collapsed article', () => {
    const rows = tree(['a', 0], ['b', 1], ['c', 2], ['d', 0]);

    expect(shape(visibleRows(rows, new Set(['a'])))).to.deep.equal([
      ['a', 0],
      ['d', 0]
    ]);
    expect(shape(visibleRows(rows, new Set(['b'])))).to.deep.equal([
      ['a', 0],
      ['b', 1],
      ['d', 0]
    ]);
    // a leaf has nothing to fold away
    expect(visibleRows(rows, new Set(['c']))).to.have.length(4);
  });

  it('reorders siblings', () => {
    const rows = tree(['a', 0], ['b', 0], ['c', 0]);

    expect(shape(moveSubtree(rows, 2, 0, 0, 3))).to.deep.equal([
      ['c', 0],
      ['a', 0],
      ['b', 0]
    ]);
  });

  it('reparents under the row it lands beneath', () => {
    const rows = tree(['a', 0], ['b', 0]);

    // asking for depth 1 under a root makes it that root's child
    expect(shape(moveSubtree(rows, 1, 2, 1, 3))).to.deep.equal([
      ['a', 0],
      ['b', 1]
    ]);
    // asking for more than one level below the row above is clamped
    expect(shape(moveSubtree(rows, 1, 2, 2, 3))).to.deep.equal([
      ['a', 0],
      ['b', 1]
    ]);
  });

  it('moves a subtree with its root', () => {
    const rows = tree(['a', 0], ['b', 1], ['c', 2], ['d', 0]);

    expect(shape(moveSubtree(rows, 1, 4, 1, 3))).to.deep.equal([
      ['a', 0],
      ['d', 0],
      ['b', 1],
      ['c', 2]
    ]);
  });

  it('leaves room under the cap for the descendants that travel too', () => {
    // c could sit two levels in as far as the row above it goes, but its
    // own child would then be past the cap - so it stops one level short
    expect(
      shape(
        moveSubtree(tree(['a', 0], ['b', 1], ['c', 0], ['d', 1]), 2, 2, 2, 3)
      )
    ).to.deep.equal([
      ['a', 0],
      ['b', 1],
      ['c', 1],
      ['d', 2]
    ]);

    // a leaf brings nothing with it and can go as deep as the cap allows
    expect(
      shape(moveSubtree(tree(['a', 0], ['b', 1], ['c', 0]), 2, 2, 2, 3))
    ).to.deep.equal([
      ['a', 0],
      ['b', 1],
      ['c', 2]
    ]);
  });

  it('refuses a move that has nowhere to land', () => {
    const rows = tree(['a', 0], ['b', 1], ['c', 2]);

    // a subtree can't be dropped inside itself
    expect(moveSubtree(rows, 0, 1, 0, 3)).to.be.null;
    expect(moveSubtree(rows, 0, 2, 0, 3)).to.be.null;
    // dropping past the end of its own subtree is a real move
    expect(moveSubtree(rows, 0, 3, 0, 3)).to.not.be.null;
    // as is a row that isn't there at all
    expect(moveSubtree(rows, 9, 0, 0, 3)).to.be.null;
  });

  it('closes a gap a move would otherwise leave', () => {
    // dropping a root between a parent and its child leaves that child
    // claiming a grandparent that is no longer above it
    expect(
      shape(
        moveSubtree(tree(['a', 0], ['b', 1], ['c', 2], ['d', 0]), 3, 2, 0, 3)
      )
    ).to.deep.equal([
      ['a', 0],
      ['b', 1],
      ['d', 0],
      ['c', 1]
    ]);
  });

  it('reads a parent out of the order as the nearest shallower row', () => {
    expect(toOrder(tree(['a', 0], ['b', 1], ['c', 2], ['d', 1]))).to.deep.equal(
      [
        { uuid: 'a', parent: null, sort_order: 0 },
        { uuid: 'b', parent: 'a', sort_order: 1 },
        { uuid: 'c', parent: 'b', sort_order: 2 },
        { uuid: 'd', parent: 'a', sort_order: 3 }
      ]
    );
  });
});
