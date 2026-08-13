/**
 * A page bakes in its workspace at render time (`window.workspace`), so a user
 * who switches workspace elsewhere - another tab, a menu action - leaves this
 * page rendering data it can no longer fetch. The server tells us on every
 * response which workspace the session is actually in, so the page can notice
 * it has been left behind and reload itself into the current one.
 */

export const WORKSPACE_HEADER = 'X-Temba-Workspace';

// asked without a workspace of our own, so the answer names the session's
const WORKSPACE_ENDPOINT = '/api/v2/workspace.json';

let stale = false;
let confirming: Promise<void> = null;

/** Test seam - reloading the page would take the test runner with it. */
export const pageReloader = {
  reload: () => window.location.reload()
};

/** The workspace this page was rendered for, if any. */
export const getPageWorkspaceUUID = (): string | null =>
  (window as any).workspace?.uuid || null;

export const isWorkspaceStale = (): boolean => stale;

/** Test hook - a page only goes stale once, and then it reloads. */
export const resetWorkspaceStale = (): void => {
  stale = false;
  confirming = null;
};

/**
 * Reloads the page into the workspace the session is now in. Unsaved work is
 * the user's to keep, so this goes through the same dirty check that page
 * navigation does - the store is asked directly rather than imported, since
 * everything it imports leads back here.
 */
export const markWorkspaceStale = (): void => {
  if (stale) {
    return;
  }
  stale = true;

  const store = document.querySelector('temba-store') as any;
  const unsaved = store?.getDirtyMessage ? store.getDirtyMessage() : null;
  if (unsaved && !window.confirm(unsaved)) {
    return;
  }

  pageReloader.reload();
};

/**
 * Asks which workspace the session is in and reloads if it isn't ours. Used
 * where a response only hints at a switch: being refused without a workspace
 * names one is how the middleware rejects a request for a workspace we've
 * left, but it's also what anything in front of the app returns, so the hint
 * is worth confirming before taking the page out from under someone.
 */
export const confirmWorkspaceStale = (): Promise<void> => {
  if (stale || confirming) {
    return confirming || Promise.resolve();
  }

  confirming = fetch(WORKSPACE_ENDPOINT, {
    method: 'GET',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
    .then((response) => {
      const current = response.headers?.get(WORKSPACE_HEADER);
      if (current && current !== getPageWorkspaceUUID()) {
        markWorkspaceStale();
      }
    })
    .catch(() => {
      // couldn't ask, so we don't know - the next response can try again
    })
    .finally(() => {
      confirming = null;
    });

  return confirming;
};

interface WorkspaceCheckable {
  status: number;
  type?: string;
  headers?: Headers;
}

/**
 * Checks a response against the workspace this page asked for. Takes the
 * headers we actually sent, since only a request that asserted a workspace can
 * be answered for a different one.
 */
export const checkWorkspaceResponse = (
  sentHeaders: { [key: string]: string },
  response: WorkspaceCheckable
): boolean => {
  const expected = getPageWorkspaceUUID();

  // either the page has no workspace, or we deliberately didn't assert one -
  // staff servicing sends the workspace it is servicing instead, and the
  // response will name that workspace rather than ours
  if (!expected || sentHeaders?.[WORKSPACE_HEADER] !== expected) {
    return false;
  }

  // cross origin responses don't expose our headers, so a missing one there
  // says nothing about the workspace
  if (response.type === 'cors' || response.type === 'opaque') {
    return false;
  }

  const actual = response.headers?.get(WORKSPACE_HEADER);
  if (actual) {
    if (actual !== expected) {
      markWorkspaceStale();
      return true;
    }
    return false;
  }

  if (response.status === 403) {
    confirmWorkspaceStale();
    return true;
  }

  return false;
};
