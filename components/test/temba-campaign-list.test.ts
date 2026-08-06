import { assert, expect } from '@open-wc/testing';
import * as sinon from 'sinon';
import { CustomEventType } from '../src/interfaces';
import { CampaignList } from '../src/list/CampaignList';
import { getComponent } from './utils.test';

const TAG = 'temba-campaign-list';
const getCampaignList = async (attrs: any = {}, width = 400, height = 0) => {
  return (await getComponent(TAG, attrs, '', width, height)) as CampaignList;
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

describe('temba-campaign-list', () => {
  it('can be created', async () => {
    const list: CampaignList = await getCampaignList();
    assert.instanceOf(list, CampaignList);
    expect(list.valueKey).to.equal('uuid');
  });

  it('opens the campaign read page for a row', async () => {
    const list: CampaignList = await getCampaignList();
    expect((list as any).getRowHref({ uuid: 'camp-1' })).to.equal(
      '/campaign/read/camp-1/'
    );
  });

  it('navigates to the group view when the group pill is clicked', async () => {
    const list: CampaignList = await getCampaignList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handleGroupClick({ uuid: 'group-1', name: 'Mothers' }, event);

    // the row's navigation must not also fire
    expect(event.stopPropagation.called).to.be.true;
    expect(fired).to.have.length(1);
    expect(fired[0].url).to.equal('/contact/group/group-1/');
  });

  it('opens the group view in a new tab on meta/ctrl-click', async () => {
    const list: CampaignList = await getCampaignList();
    const openStub = sinon.stub(window, 'open');
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    try {
      (list as any).handleGroupClick(
        { uuid: 'group-1', name: 'Mothers' },
        makeClick({ metaKey: true })
      );

      expect(openStub.calledWith('/contact/group/group-1/', '_blank')).to.be
        .true;
      // no in-app redirect when opening a new tab
      expect(fired).to.have.length(0);
    } finally {
      openStub.restore();
    }
  });

  it('intercepts a real click on a rendered group pill', async () => {
    const list: CampaignList = await getCampaignList();
    // render a single row carrying a group pill
    (list as any).items = [
      {
        uuid: 'camp-1',
        name: 'Vaccination Reminders',
        group: { uuid: 'group-1', name: 'Mothers' }
      }
    ];
    list.requestUpdate();
    await list.updateComplete;

    const pill = list.shadowRoot.querySelector('temba-label') as HTMLElement;
    expect(pill, 'group pill rendered').to.exist;

    const redirects: any[] = [];
    const rowClicks: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      redirects.push(e.detail)
    );
    list.addEventListener(CustomEventType.RowClick, (e: any) =>
      rowClicks.push(e.detail)
    );

    pill.dispatchEvent(
      new MouseEvent('click', { bubbles: true, composed: true })
    );

    // the pill navigates, and the row's campaign navigation is suppressed
    expect(redirects).to.have.length(1);
    expect(redirects[0].url).to.equal('/contact/group/group-1/');
    expect(rowClicks, 'row click suppressed').to.have.length(0);
  });

  it('opens the campaign on a click outside the pill', async () => {
    const list: CampaignList = await getCampaignList();
    // a row that carries a group pill, so we can click *around* it
    (list as any).items = [
      {
        uuid: 'camp-1',
        name: 'Vaccination Reminders',
        group: { uuid: 'group-1', name: 'Mothers' }
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

    // click the row itself (not the pill) — navigation falls through to
    // the campaign read page
    row.dispatchEvent(
      new MouseEvent('click', { bubbles: true, composed: true })
    );

    expect(redirects).to.have.length(1);
    expect(redirects[0].url).to.equal('/campaign/read/camp-1/');
  });

  it('ignores a group with no uuid', async () => {
    const list: CampaignList = await getCampaignList();
    const fired: any[] = [];
    list.addEventListener(CustomEventType.Redirected, (e: any) =>
      fired.push(e.detail)
    );

    const event = makeClick();
    (list as any).handleGroupClick({ name: 'Mothers' } as any, event);

    // still swallows the click so the row doesn't navigate...
    expect(event.stopPropagation.called).to.be.true;
    // ...but there's nowhere to go
    expect(fired).to.have.length(0);
  });

  it('renders a row without a group', async () => {
    const list: CampaignList = await getCampaignList();
    (list as any).items = [
      {
        uuid: 'camp-1',
        name: 'Vaccination Reminders',
        group: null,
        events: 0,
        contacts: 0
      }
    ];
    list.requestUpdate();
    await list.updateComplete;

    const row = list.shadowRoot.querySelector('tr.row') as HTMLElement;
    expect(row, 'row rendered').to.exist;
    expect(list.shadowRoot.querySelector('temba-label')).to.not.exist;
  });
});
