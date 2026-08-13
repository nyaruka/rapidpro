import { assert, expect, fixture } from '@open-wc/testing';
import { WorkspaceNotice } from '../src/display/WorkspaceNotice';
import { deleteRequest, getUrl, postUrl } from '../src/utils';
import {
  WORKSPACE_HEADER,
  checkWorkspaceResponse,
  isWorkspaceStale,
  markWorkspaceStale,
  onWorkspaceStale,
  resetWorkspaceStale
} from '../src/workspace';
import {
  assertScreenshot,
  clearMockGets,
  clearMockPosts,
  getClip,
  mockGET,
  mockPOST
} from './utils.test';

const PAGE_WORKSPACE = '11111111-1111-4111-8111-111111111111';
const OTHER_WORKSPACE = '22222222-2222-4222-8222-222222222222';

const setPageWorkspace = (uuid: string) => {
  if (uuid) {
    (window as any).workspace = { uuid };
  } else {
    delete (window as any).workspace;
  }
};

const createNotice = async () => {
  return (await fixture(
    '<temba-workspace-notice></temba-workspace-notice>'
  )) as WorkspaceNotice;
};

// a store the notice can read the current workspace name from
const withStore = (name: string) => {
  const store = document.createElement('temba-store');
  (store as any).getWorkspace = () => (name ? { name } : null);
  document.body.appendChild(store);
  return () => store.remove();
};

describe('workspace staleness', () => {
  let previousWorkspace: any;

  beforeEach(() => {
    previousWorkspace = (window as any).workspace;
    setPageWorkspace(PAGE_WORKSPACE);
    resetWorkspaceStale();
  });

  afterEach(() => {
    (window as any).workspace = previousWorkspace;
    resetWorkspaceStale();
    clearMockGets();
    clearMockPosts();
  });

  it('leaves the page alone when the response is for the same workspace', async () => {
    mockGET(
      /\/api\/v2\/fresh\.json/,
      {},
      { [WORKSPACE_HEADER]: PAGE_WORKSPACE }
    );
    await getUrl('/api/v2/fresh.json');

    expect(isWorkspaceStale()).to.equal(false);
  });

  it('marks the page stale when the response names another workspace', async () => {
    mockGET(
      /\/api\/v2\/switched\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await getUrl('/api/v2/switched.json');

    expect(isWorkspaceStale()).to.equal(true);
  });

  it('marks the page stale when a request is rejected without a workspace', async () => {
    // the middleware rejects a request for the wrong workspace before it sets
    // the response header, so this is the shape of that rejection
    mockGET(/\/api\/v2\/rejected\.json/, {}, {}, '403');

    try {
      await getUrl('/api/v2/rejected.json');
      assert.fail('expected the request to be rejected');
    } catch (error) {
      // expected
    }

    expect(isWorkspaceStale()).to.equal(true);
  });

  it('leaves the page alone when our own workspace forbids us', async () => {
    mockGET(
      /\/api\/v2\/forbidden\.json/,
      {},
      { [WORKSPACE_HEADER]: PAGE_WORKSPACE },
      '403'
    );

    try {
      await getUrl('/api/v2/forbidden.json');
      assert.fail('expected the request to be rejected');
    } catch (error) {
      // expected
    }

    expect(isWorkspaceStale()).to.equal(false);
  });

  it('leaves the page alone while servicing another workspace', async () => {
    // servicing deliberately asks for a workspace other than the page's, so
    // the workspace it answers with says nothing about the session
    mockGET(
      /\/api\/v2\/serviced\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await getUrl('/api/v2/serviced.json', null, {
      'X-Temba-Service-Org': '1234'
    });

    expect(isWorkspaceStale()).to.equal(false);
  });

  it('marks the page stale from a post', async () => {
    mockPOST(
      /\/api\/v2\/posted\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await postUrl('/api/v2/posted.json', {});

    expect(isWorkspaceStale()).to.equal(true);
  });

  it('marks the page stale from a delete', async () => {
    mockPOST(
      /\/api\/v2\/deleted\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await deleteRequest('/api/v2/deleted.json');

    expect(isWorkspaceStale()).to.equal(true);
  });

  it('ignores responses it cannot read headers from', () => {
    const sent = { [WORKSPACE_HEADER]: PAGE_WORKSPACE };
    const headers = new Headers();

    expect(
      checkWorkspaceResponse(sent, { status: 403, type: 'cors', headers })
    ).to.equal(false);
    expect(
      checkWorkspaceResponse(sent, { status: 403, type: 'opaque', headers })
    ).to.equal(false);
    expect(isWorkspaceStale()).to.equal(false);
  });

  it('ignores responses when the page has no workspace', () => {
    setPageWorkspace(null);

    const headers = new Headers({ [WORKSPACE_HEADER]: OTHER_WORKSPACE });
    expect(checkWorkspaceResponse({}, { status: 200, headers })).to.equal(
      false
    );
    expect(isWorkspaceStale()).to.equal(false);
  });

  it('notifies listeners once', () => {
    let notified = 0;
    const unsubscribe = onWorkspaceStale(() => notified++);

    markWorkspaceStale();
    markWorkspaceStale();
    expect(notified).to.equal(1);

    unsubscribe();
    resetWorkspaceStale();
    markWorkspaceStale();
    expect(notified).to.equal(1);
  });
});

describe('temba-workspace-notice', () => {
  let previousWorkspace: any;

  beforeEach(() => {
    previousWorkspace = (window as any).workspace;
    setPageWorkspace(PAGE_WORKSPACE);
    resetWorkspaceStale();
  });

  afterEach(() => {
    (window as any).workspace = previousWorkspace;
    resetWorkspaceStale();
  });

  it('shows nothing until the page goes stale', async () => {
    const notice = await createNotice();

    assert.instanceOf(notice, WorkspaceNotice);
    expect(notice.shadowRoot.querySelector('temba-alert')).to.equal(null);
  });

  it('names the workspace the page is showing', async () => {
    const removeStore = withStore('Nyaruka');
    const notice = await createNotice();

    markWorkspaceStale();
    await notice.updateComplete;

    const alert = notice.shadowRoot.querySelector('temba-alert');
    expect(alert).to.not.equal(null);
    expect(alert.textContent).to.contain('Nyaruka');

    await assertScreenshot(
      'workspace-notice/stale',
      getClip(alert as HTMLElement)
    );
    removeStore();
  });

  it('manages without a workspace name', async () => {
    const notice = await createNotice();

    markWorkspaceStale();
    await notice.updateComplete;

    const alert = notice.shadowRoot.querySelector('temba-alert');
    expect(alert.textContent).to.contain('switched away from');
  });

  it('shows a page that was already stale before it was added', async () => {
    markWorkspaceStale();
    const notice = await createNotice();

    expect(notice.stale).to.equal(true);
  });

  it('stops listening once removed', async () => {
    const notice = await createNotice();
    notice.remove();

    markWorkspaceStale();
    await notice.updateComplete;

    expect(notice.stale).to.equal(false);
  });
});
