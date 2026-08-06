import { assert, expect, fixture, html, oneEvent } from '@open-wc/testing';
import * as sinon from 'sinon';
import { CustomEventType } from '../src/interfaces';
import { FlowList } from '../src/list/FlowList';
import { Store } from '../src/store/Store';
import { setRealtimeContext } from '../src/live/Realtime';
import { setSocketProvider } from '../src/live/SocketService';
import {
  getComponent,
  mockAssetResolver,
  MockSocketProvider
} from './utils.test';

const TAG = 'temba-flow-list';
const getFlowList = async (attrs: any = {}, width = 400, height = 0) => {
  return (await getComponent(TAG, attrs, '', width, height)) as FlowList;
};

// a plain click with no modifier keys, carrying the stopPropagation /
// preventDefault spies the handler is expected to call
const makeClick = (over: any = {}) =>
  ({
    metaKey: false,
    ctrlKey: false,
    stopPropagation: sinon.spy(),
    preventDefault: sinon.spy(),
    ...over
  }) as any;

describe('temba-flow-list', () => {
  it('can be created', async () => {
    const list: FlowList = await getFlowList();
    assert.instanceOf(list, FlowList);
    expect(list.valueKey).to.equal('uuid');
  });

  it('opens the flow editor for a row', async () => {
    const list: FlowList = await getFlowList();
    expect((list as any).getRowHref({ uuid: 'flow-1' })).to.equal(
      '/flow/editor/flow-1/'
    );
  });

  it('seeds the store from a fetched page and keeps row names current', async () => {
    const flowUuid = 'f-001';
    const socket = new MockSocketProvider();
    const previousProvider = setSocketProvider(socket);
    let wrapper: HTMLElement;

    try {
      mockAssetResolver();
      wrapper = await fixture(
        html`<div>
          <temba-store
            org="org-uuid"
            user="user-uuid"
            assets="/test-assets/store/assets.json"
          ></temba-store>
          <temba-flow-list></temba-flow-list>
        </div>`
      );
      const store = wrapper.querySelector('temba-store') as Store;
      const list = wrapper.querySelector('temba-flow-list') as FlowList;
      await store.initialHttpComplete;
      await store.resolveAssets([{ type: 'flow', uuid: flowUuid }]);
      expect(store.getAsset('flow', flowUuid).name).to.equal(
        'Canonical Welcome Campaign'
      );
      const fetched = oneEvent(list, CustomEventType.FetchComplete, false);
      list.endpoint = '/test-assets/content-list/flows.json';
      await fetched;

      // the fetched page is newer than anything cached, so it wins and
      // replaces what the store had
      expect((list as any).items[0].name).to.equal('Welcome Campaign');
      expect((list as any).items[0].runs).to.equal(12450);
      expect(store.getAsset('flow', flowUuid).name).to.equal(
        'Welcome Campaign'
      );

      socket.serverPublish('org:org-uuid', {
        type: 'asset_changed',
        asset: { type: 'flow', uuid: flowUuid, name: 'Renamed Child Flow' }
      });
      await list.updateComplete;

      expect((list as any).items[0].name).to.equal('Renamed Child Flow');
      expect((list as any).items[1].name).to.equal('IVR Survey');
      expect(
        list.shadowRoot.querySelector('tr.row .flow-name .name').textContent
      ).to.equal('Renamed Child Flow');
    } finally {
      wrapper?.remove();
      setRealtimeContext(null);
      setSocketProvider(previousProvider);
    }
  });

  it('navigates to the label view when a label chip is clicked', async () => {
    const list: FlowList = await getFlowList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handleLabelClick(
      { uuid: 'label-1', name: 'Important' },
      event
    );

    // the row's navigation must not also fire
    expect(event.stopPropagation.called).to.be.true;
    expect(fired).to.have.length(1);
    expect(fired[0].url).to.equal('/flow/filter/label-1/');
  });

  it('opens the label view in a new tab on meta/ctrl-click', async () => {
    const list: FlowList = await getFlowList();
    const openStub = sinon.stub(window, 'open');
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    try {
      (list as any).handleLabelClick(
        { uuid: 'label-1', name: 'Important' },
        makeClick({ metaKey: true })
      );

      expect(openStub.calledWith('/flow/filter/label-1/', '_blank')).to.be.true;
      // no in-app redirect when opening a new tab
      expect(fired).to.have.length(0);
    } finally {
      openStub.restore();
    }
  });

  it('intercepts a real click on a rendered label chip', async () => {
    const list: FlowList = await getFlowList();
    // render a single row carrying a label chip
    (list as any).items = [
      {
        uuid: 'flow-1',
        name: 'Flow 1',
        labels: [{ uuid: 'label-1', name: 'Important' }]
      }
    ];
    list.requestUpdate();
    await list.updateComplete;

    const chip = list.shadowRoot.querySelector('temba-label') as HTMLElement;
    expect(chip, 'label chip rendered').to.exist;

    const redirects: any[] = [];
    const rowClicks: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      redirects.push(e.detail)
    );
    list.addEventListener(CustomEventType.RowClick, (e: any) =>
      rowClicks.push(e.detail)
    );

    chip.dispatchEvent(
      new MouseEvent('click', { bubbles: true, composed: true })
    );

    // the label navigates, and the row's flow-editor navigation is suppressed
    expect(redirects).to.have.length(1);
    expect(redirects[0].url).to.equal('/flow/filter/label-1/');
    expect(rowClicks, 'row click suppressed').to.have.length(0);
  });

  it('opens the flow editor on a click outside a chip', async () => {
    const list: FlowList = await getFlowList();
    // a row that carries a label chip, so we can click *around* it
    (list as any).items = [
      {
        uuid: 'flow-1',
        name: 'Flow 1',
        labels: [{ uuid: 'label-1', name: 'Important' }]
      }
    ];
    list.requestUpdate();
    await list.updateComplete;

    const row = list.shadowRoot.querySelector('tr.row') as HTMLElement;
    expect(row, 'row rendered').to.exist;

    const redirects: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      redirects.push(e.detail)
    );

    // click the row itself (not the chip) — navigation falls through to
    // the editor
    row.dispatchEvent(
      new MouseEvent('click', { bubbles: true, composed: true })
    );

    expect(redirects).to.have.length(1);
    expect(redirects[0].url).to.equal('/flow/editor/flow-1/');
  });

  it('ignores a label with no uuid', async () => {
    const list: FlowList = await getFlowList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handleLabelClick({ name: 'Important' } as any, event);

    // still swallows the click so the row doesn't navigate...
    expect(event.stopPropagation.called).to.be.true;
    // ...but there's nowhere to go
    expect(fired).to.have.length(0);
  });
});
