/**
 * A page bakes in its workspace at render time (`window.workspace`), so a user
 * who switches workspace elsewhere - another tab, a menu action - leaves this
 * page rendering data it can no longer fetch. The server tells us on every
 * response which workspace the session is actually in, so the page can notice
 * it has been left behind and offer a refresh.
 */

export const WORKSPACE_HEADER = 'X-Temba-Workspace';

type StaleListener = () => void;

let stale = false;
const listeners = new Set<StaleListener>();

/** The workspace this page was rendered for, if any. */
export const getPageWorkspaceUUID = (): string | null =>
  (window as any).workspace?.uuid || null;

export const isWorkspaceStale = (): boolean => stale;

/**
 * Records that this page is showing a workspace the user has since left. It's
 * a one-way trip - switching back isn't something this page can observe, and a
 * page that has been denied content is already showing gaps.
 */
export const markWorkspaceStale = (): void => {
  if (stale) {
    return;
  }
  stale = true;
  listeners.forEach((listener) => listener());
};

/** Registers interest in the page going stale, returning an unsubscribe. */
export const onWorkspaceStale = (listener: StaleListener): (() => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Test hook - the page itself never recovers from being stale. */
export const resetWorkspaceStale = (): void => {
  stale = false;
  listeners.clear();
};

interface WorkspaceCheckable {
  status: number;
  type?: string;
  headers?: Headers;
}

/**
 * Checks a response against the workspace this page asked for, marking the
 * page stale on a mismatch. Takes the headers we actually sent, since only a
 * request that asserted a workspace can be answered for a different one.
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

  // a request for the wrong workspace is rejected before the response header
  // is set, so a 403 without one is that rejection - anything else that
  // forbids us is answered by the workspace we asked for and carries it
  if (response.status === 403) {
    markWorkspaceStale();
    return true;
  }

  return false;
};
