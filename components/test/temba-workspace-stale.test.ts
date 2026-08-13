import { assert, expect } from '@open-wc/testing';
import { SinonStub, stub } from 'sinon';
import { deleteRequest, getUrl, postUrl } from '../src/utils';
import {
  WORKSPACE_HEADER,
  checkWorkspaceResponse,
  confirmWorkspaceStale,
  isWorkspaceStale,
  markWorkspaceStale,
  pageReloader,
  resetWorkspaceStale
} from '../src/workspace';
import { clearMockGets, clearMockPosts, mockGET, mockPOST } from './utils.test';

const PAGE_WORKSPACE = '11111111-1111-4111-8111-111111111111';
const OTHER_WORKSPACE = '22222222-2222-4222-8222-222222222222';

const setPageWorkspace = (uuid: string) => {
  if (uuid) {
    (window as any).workspace = { uuid };
  } else {
    delete (window as any).workspace;
  }
};

// what the session answers when asked which workspace it's in
const mockCurrentWorkspace = (uuid: string, status = '200') => {
  mockGET(
    /\/api\/v2\/workspace\.json/,
    {},
    uuid ? { [WORKSPACE_HEADER]: uuid } : {},
    status
  );
};

// a store carrying unsaved work, which the reload has to ask about first
const withUnsavedChanges = (message: string) => {
  const store = document.createElement('temba-store');
  (store as any).getDirtyMessage = () => message;
  document.body.appendChild(store);
  return () => store.remove();
};

describe('workspace staleness', () => {
  let previousWorkspace: any;
  let reload: SinonStub;

  beforeEach(() => {
    previousWorkspace = (window as any).workspace;
    setPageWorkspace(PAGE_WORKSPACE);
    resetWorkspaceStale();
    reload = stub(pageReloader, 'reload');
  });

  afterEach(() => {
    (window as any).workspace = previousWorkspace;
    resetWorkspaceStale();
    reload.restore();
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
    expect(reload.callCount).to.equal(0);
  });

  it('reloads when the response names another workspace', async () => {
    mockGET(
      /\/api\/v2\/switched\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await getUrl('/api/v2/switched.json');

    expect(isWorkspaceStale()).to.equal(true);
    expect(reload.callCount).to.equal(1);
  });

  it('reloads only once, however many responses say so', async () => {
    mockGET(
      /\/api\/v2\/switched\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await getUrl('/api/v2/switched.json');
    await getUrl('/api/v2/switched.json');

    expect(reload.callCount).to.equal(1);
  });

  it('confirms the switch before reloading on a refusal', async () => {
    // the middleware rejects a request for the wrong workspace before it sets
    // the response header, so this is the shape of that rejection
    mockGET(/\/api\/v2\/rejected\.json/, {}, {}, '403');
    mockCurrentWorkspace(OTHER_WORKSPACE);

    try {
      await getUrl('/api/v2/rejected.json');
      assert.fail('expected the request to be rejected');
    } catch (error) {
      // expected
    }
    await confirmWorkspaceStale();

    expect(reload.callCount).to.equal(1);
  });

  it('stays put when a refusal came from somewhere else', async () => {
    // anything in front of the app forbids us the same way, but the session is
    // still in our workspace, so there is nothing to reload into
    mockGET(/\/api\/v2\/blocked\.json/, {}, {}, '403');
    mockCurrentWorkspace(PAGE_WORKSPACE);

    try {
      await getUrl('/api/v2/blocked.json');
      assert.fail('expected the request to be rejected');
    } catch (error) {
      // expected
    }
    await confirmWorkspaceStale();

    expect(isWorkspaceStale()).to.equal(false);
    expect(reload.callCount).to.equal(0);
  });

  it('stays put when it cannot ask which workspace we are in', async () => {
    mockCurrentWorkspace(null, '403');

    await confirmWorkspaceStale();

    expect(reload.callCount).to.equal(0);
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
    expect(reload.callCount).to.equal(0);
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
    expect(reload.callCount).to.equal(0);
  });

  it('reloads from a post', async () => {
    mockPOST(
      /\/api\/v2\/posted\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await postUrl('/api/v2/posted.json', {});

    expect(reload.callCount).to.equal(1);
  });

  it('reloads from a delete', async () => {
    mockPOST(
      /\/api\/v2\/deleted\.json/,
      {},
      { [WORKSPACE_HEADER]: OTHER_WORKSPACE }
    );
    await deleteRequest('/api/v2/deleted.json');

    expect(reload.callCount).to.equal(1);
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
    expect(reload.callCount).to.equal(0);
  });

  it('ignores responses when the page has no workspace', () => {
    setPageWorkspace(null);

    const headers = new Headers({ [WORKSPACE_HEADER]: OTHER_WORKSPACE });
    expect(checkWorkspaceResponse({}, { status: 200, headers })).to.equal(
      false
    );
    expect(reload.callCount).to.equal(0);
  });

  it('asks before taking unsaved work with it', () => {
    const removeStore = withUnsavedChanges('You have unsaved changes');
    const confirmed = stub(window, 'confirm').returns(false);

    markWorkspaceStale();

    expect(confirmed.callCount).to.equal(1);
    expect(reload.callCount).to.equal(0);

    confirmed.restore();
    removeStore();
  });

  it('reloads when the unsaved work is theirs to lose', () => {
    const removeStore = withUnsavedChanges('You have unsaved changes');
    const confirmed = stub(window, 'confirm').returns(true);

    markWorkspaceStale();

    expect(reload.callCount).to.equal(1);

    confirmed.restore();
    removeStore();
  });

  it('is reachable from the page, which fetches outside the components', async () => {
    expect(typeof (window as any).confirmWorkspaceStale).to.equal('function');

    mockCurrentWorkspace(OTHER_WORKSPACE);
    await (window as any).confirmWorkspaceStale();

    expect(reload.callCount).to.equal(1);
  });
});
