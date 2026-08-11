import { assert, expect } from '@open-wc/testing';
import * as sinon from 'sinon';

import { TembaMenu } from '../src/list/TembaMenu';
import { NotificationList } from '../src/list/NotificationList';
import { setRealtimeContext } from '../src/live/Realtime';
import { setSocketProvider, SocketProvider } from '../src/live/SocketService';
import { CustomEventType } from '../src/interfaces';
import {
  assertScreenshot,
  clearMockPosts,
  getClip,
  getComponent,
  mockPOST,
  MockSocketProvider
} from './utils.test';
import { extractInitials } from '../src/utils';

const TAG = 'temba-menu';
const getMenu = async (attrs: any = {}, width = 0) => {
  const menu = (await getComponent(
    TAG,
    attrs,
    '',
    width,
    0,
    'display:inline-block'
  )) as TembaMenu;

  // wait for the fetch
  await menu.httpComplete;

  return menu;
};

const IDX_TASKS = 1;
const IDX_SCHEDULE = 2;

describe('temba-menu', () => {
  it('can be created', async () => {
    const list: TembaMenu = await getMenu();
    assert.instanceOf(list, TembaMenu);
    expect(list.root).is.undefined;
  });

  it('renders with endpoint', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });

    expect(menu.root.items.length).to.equal(3);
    await assertScreenshot('menu/menu-root', getClip(menu));
  });

  it('supports submenu', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });

    // click our tasks
    menu.getDiv('#menu-tasks').click();
    await menu.httpComplete;
    menu.requestUpdate();
    // await menu.updateComplete;

    expect(menu.root.items[IDX_TASKS].items.length).to.equal(3);
    await assertScreenshot('menu/menu-submenu', getClip(menu));
  });

  it('sets focus', async () => {
    // setting focus just shows the selection, it does
    // not trigger events such as loading or dispatching

    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });

    // click our tasks
    menu.getDiv('#menu-tasks').click();
    await menu.httpComplete;

    // setFocusedItem is async and arms a debounced refresh of the selection
    // path - leaving it in flight lets that refresh land in the middle of
    // what follows
    await menu.setFocusedItem('schedule');

    // setting focus does NOT fetch items
    expect(menu.root.items[IDX_SCHEDULE].items).to.equal(undefined);

    // now load the items explicitly
    menu.getDiv('#menu-schedule').click();
    await menu.httpComplete;
    expect(menu.root.items[IDX_SCHEDULE].items.length).to.equal(3);

    await assertScreenshot('menu/menu-focused-with items', getClip(menu));

    await menu.setFocusedItem('tasks');
    await assertScreenshot('menu/menu-tasks', getClip(menu));

    await menu.setFocusedItem('tasks/todo');
    await assertScreenshot('menu/menu-tasks-nextup', getClip(menu));
  });

  it('survives a level reloading while one of its items is loading', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });
    const schedule = menu.root.items[IDX_SCHEDULE];

    // load an item's children, then reload the level underneath it before
    // those children land - which is what a debounced refresh firing during
    // a click does
    menu.getDiv('#menu-schedule').click();
    menu.reset();
    await menu.httpComplete;

    // the reload reused the item rather than swapping in a copy, so the
    // children landed somewhere still in the tree
    assert.strictEqual(menu.root.items[IDX_SCHEDULE], schedule);
    expect(menu.root.items[IDX_SCHEDULE].items.length).to.equal(3);
  });

  it('waits for every load in flight', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });

    // two overlapping loads - awaiting has to cover both, not just whichever
    // one was started last
    menu.getDiv('#menu-tasks').click();
    menu.getDiv('#menu-schedule').click();
    await menu.httpComplete;

    expect(menu.root.items[IDX_TASKS].items.length).to.equal(3);
    expect(menu.root.items[IDX_SCHEDULE].items.length).to.equal(3);
  });

  it('refreshes', async () => {
    // the menu should refresh along the selection path without destroying state
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-root.json'
    });

    // click our tasks
    menu.getDiv('#menu-tasks').click();
    menu.requestUpdate();
    await menu.httpComplete;
    // await menu.updateComplete;

    // now click on the todo
    menu.getDiv('#menu-todo').click();
    menu.requestUpdate();
    // await menu.updateComplete;

    expect(menu.root.items[IDX_TASKS].items.length).to.equal(3);
    await assertScreenshot('menu/menu-refresh-1', getClip(menu));

    // now refresh!
    menu.refresh();
    await menu.httpComplete;

    // we should still have our task items
    expect(menu.root.items[IDX_TASKS].items.length).to.equal(3);
    await assertScreenshot('menu/menu-refresh-2', getClip(menu));
  });
});

describe('temba-menu notifications', () => {
  const CHANNEL = 'notifications:org-uuid:user-uuid';

  let mockSocket: MockSocketProvider;
  let previousProvider: SocketProvider;

  beforeEach(() => {
    mockSocket = new MockSocketProvider();
    previousProvider = setSocketProvider(mockSocket);
    setRealtimeContext({ org: 'org-uuid', user: 'user-uuid' });

    // the mark-all-seen delete fired on popup open
    clearMockPosts();
    mockPOST(/test-assets\/list\/notifications\.json/, {});
  });

  afterEach(() => {
    setRealtimeContext(null);
    setSocketProvider(previousProvider);
  });

  const getNotificationsMenu = async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-notifications.json'
    });

    // wait for the embedded notification list to finish its initial fetch
    const list = menu.shadowRoot.querySelector(
      'temba-notification-list'
    ) as NotificationList;
    if (list.items.length === 0) {
      await new Promise<void>((resolve) => {
        list.addEventListener(
          CustomEventType.FetchComplete,
          () => {
            resolve();
          },
          { once: true }
        );
      });
    }
    await menu.updateComplete;
    return { menu, list };
  };

  const getNotificationsItem = (menu: TembaMenu) => {
    return menu.root.items.find((item) => item.id === 'notifications');
  };

  it('lights the unseen badge when a notification arrives', async () => {
    const { menu } = await getNotificationsMenu();
    expect(getNotificationsItem(menu).bubble).to.equal(null);

    mockSocket.publish(CHANNEL, {
      type: 'tickets:activity',
      created_on: '2021-03-31T00:00:00.000000Z',
      url: '/notification/read/4/',
      is_seen: false
    });

    await menu.updateComplete;
    expect(getNotificationsItem(menu).bubble).to.equal('tomato');
    await assertScreenshot('menu/menu-notification-bubble', getClip(menu));
  });

  it('no longer refreshes embedded lists on menu refresh', async () => {
    const { menu, list } = await getNotificationsMenu();
    const listRefresh = sinon.spy(list, 'refresh');

    await menu.doRefresh();
    expect(listRefresh.called).to.equal(false);
  });

  it('marks seen and clears the badge when the popup opens', async () => {
    const { menu, list } = await getNotificationsMenu();

    mockSocket.publish(CHANNEL, {
      type: 'tickets:activity',
      created_on: '2021-03-31T00:00:00.000000Z',
      url: '/notification/read/4/',
      is_seen: false
    });
    await menu.updateComplete;
    expect(getNotificationsItem(menu).bubble).to.equal('tomato');

    const listRefresh = sinon.spy(list, 'refresh');

    // open the popup
    const toggle = menu.shadowRoot.querySelector(
      '#dd-notifications div[slot="toggle"]'
    ) as HTMLDivElement;
    toggle.click();
    await menu.updateComplete;

    // everything is marked seen and the badge clears, with no refetching -
    // the socket keeps the list current
    expect(listRefresh.called).to.equal(false);
    const deleted = (window.fetch as any)
      .getCalls()
      .filter((call: any) => call.args[1]?.method === 'DELETE');
    expect(deleted.length).to.equal(1);
    expect(deleted[0].args[0]).to.equal(list.endpoint);
    expect(getNotificationsItem(menu).bubble).to.equal(null);
  });
  it('restores the badge when marking seen fails', async () => {
    clearMockPosts();
    mockPOST(/test-assets\/list\/notifications\.json/, {}, {}, '500');

    const { menu } = await getNotificationsMenu();

    mockSocket.publish(CHANNEL, {
      type: 'tickets:activity',
      created_on: '2021-03-31T00:00:00.000000Z',
      url: '/notification/read/4/',
      is_seen: false
    });
    await menu.updateComplete;
    expect(getNotificationsItem(menu).bubble).to.equal('tomato');

    const toggle = menu.shadowRoot.querySelector(
      '#dd-notifications div[slot="toggle"]'
    ) as HTMLDivElement;
    toggle.click();

    // the delete failed, so once it settles the badge comes back
    await new Promise((resolve) => setTimeout(resolve, 0));
    await menu.updateComplete;
    expect(getNotificationsItem(menu).bubble).to.equal('tomato');
  });
});

describe('avatars', () => {
  it('can generate initials from text', async () => {
    assert.equal(extractInitials(''), '?');
    assert.equal(extractInitials('~~'), '?');
    assert.equal(extractInitials('X'), 'X');
    assert.equal(extractInitials('鸡'), '鸡');
    assert.equal(extractInitials('Acme'), 'AC');
    assert.equal(extractInitials('Cool Flows'), 'CF');
    assert.equal(extractInitials('Very Cool Flows'), 'VC');
    assert.equal(extractInitials('1Password'), '1P');
    assert.equal(extractInitials('تدفقات باردة'), 'تب');
    assert.equal(extractInitials('U-Report'), 'UR');
    assert.equal(extractInitials('U-Report Nigeria'), 'UN');
    assert.equal(extractInitials('al-Jazeera'), 'AJ');
    assert.equal(extractInitials('al-Jazeera News'), 'AN');
    assert.equal(extractInitials('UNICEF - Ireland'), 'UI');
    assert.equal(extractInitials('Dave & Busters'), 'DB');
    assert.equal(extractInitials('Dave and Busters'), 'DB');
  });
});
