import { expect } from '@open-wc/testing';

import { TembaMenu } from '../src/list/TembaMenu';
import { getComponent } from './utils.test';
import { CustomEventType } from '../src/interfaces';

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
  await menu.httpComplete;
  return menu;
};

describe('temba-menu support item', () => {
  it('fires button clicked for link items in popups', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-support.json'
    });

    let clickedItem: any = null;
    menu.addEventListener(CustomEventType.ButtonClicked, (event: any) => {
      clickedItem = event.detail.item;
    });

    const supportItem = menu.getDiv('#menu-support') as HTMLElement;
    expect(supportItem, 'support item should render').to.exist;

    // mobile items should be visible on desktop too
    const style = window.getComputedStyle(supportItem);
    expect(style.display).to.not.equal('none');

    // open the popup, then click the chat link
    supportItem.click();
    await menu.updateComplete;
    const dropdown = menu.getDiv('#dd-support') as any;
    expect(dropdown.open, 'popup should open on toggle click').to.equal(true);

    const chatLink = menu.getDiv('#menu-open_chat') as HTMLElement;
    expect(chatLink, 'chat link should render').to.exist;

    chatLink.click();
    await menu.updateComplete;

    expect(clickedItem, 'button clicked event should fire').to.exist;
    expect(clickedItem.event).to.equal('temba-show-support');
    expect(dropdown.open, 'popup should close on link click').to.equal(false);
  });

  it('delegates href link navigation to the host', async () => {
    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-support.json'
    });

    let clickedItem: any = null;
    menu.addEventListener(CustomEventType.ButtonClicked, (event: any) => {
      clickedItem = event.detail.item;
    });

    // the anchor carries real attributes for affordance and middle-click
    const docsLink = menu.getDiv('#menu-help_docs') as HTMLElement;
    expect(docsLink.getAttribute('href')).to.equal('https://help.textit.com');
    expect(docsLink.getAttribute('target')).to.equal('_blank');

    // clicks are delegated to the host to navigate, like all menu items
    docsLink.click();
    await menu.updateComplete;

    expect(clickedItem, 'button clicked should fire for href links').to.exist;
    expect(clickedItem.href).to.equal('https://help.textit.com');
    expect(clickedItem.target).to.equal('_blank');
  });

  it('invokes the -temba-button-clicked attribute handler like frame.html', async () => {
    // replicate frame.js handleMenuClicked + frame_top.html listener
    let supportShown = false;
    document.addEventListener('temba-show-support', () => {
      supportShown = true;
    });
    (window as any).handleMenuClicked = (event: any) => {
      const item = event.detail.item;
      if (item.event) {
        document.dispatchEvent(new CustomEvent(item.event, { detail: item }));
      }
    };

    const menu: TembaMenu = await getMenu({
      endpoint: '/test-assets/menu/menu-support.json',
      '-temba-button-clicked': 'handleMenuClicked(event)'
    });

    const chatLink = menu.getDiv('#menu-open_chat') as HTMLElement;
    chatLink.click();
    await menu.updateComplete;

    expect(supportShown, 'temba-show-support should be dispatched').to.equal(
      true
    );
  });

  it('only shows the hamburger when collapsed on mobile', async () => {
    (window as any).isMobile = () => true;
    try {
      const menu: TembaMenu = await getMenu({
        endpoint: '/test-assets/menu/menu-support.json',
        collapsed: 'collapsed'
      });
      await menu.updateComplete;

      const hamburger = menu.getDiv('.expand-icon') as HTMLElement;
      expect(window.getComputedStyle(hamburger).display).to.not.equal('none');

      // everything else in the header should be hidden, including popups
      const support = menu.getDiv('#dd-support') as HTMLElement;
      expect(window.getComputedStyle(support).display).to.equal('none');

      const notifications = menu.getDiv('#dd-notifications') as HTMLElement;
      expect(window.getComputedStyle(notifications).display).to.equal('none');
    } finally {
      delete (window as any).isMobile;
    }
  });
});
