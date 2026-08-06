import { expect, assert } from '@open-wc/testing';
import { CanvasMenu } from '../src/flow/CanvasMenu';
import { CONTEXT_MENU_SHORTCUTS, FlowTypes } from '../src/flow/types';
import { assertScreenshot, getClip, getComponent } from './utils.test';

describe('temba-canvas-menu', () => {
  const messageShortcuts = CONTEXT_MENU_SHORTCUTS[FlowTypes.MESSAGE];
  const voiceShortcuts = CONTEXT_MENU_SHORTCUTS[FlowTypes.VOICE];
  const backgroundShortcuts = CONTEXT_MENU_SHORTCUTS[FlowTypes.BACKGROUND];

  const createCanvasMenu = async () => {
    const component = (await getComponent(
      'temba-canvas-menu',
      {},
      '',
      250,
      250
    )) as CanvasMenu;
    await component.updateComplete;
    return component;
  };

  it('can be created', async () => {
    const menu = await createCanvasMenu();
    assert.instanceOf(menu, CanvasMenu);
    expect(menu.open).to.be.false;
  });

  it('is not visible when closed', async () => {
    const menu = await createCanvasMenu();
    expect(menu.open).to.be.false;

    // verify no menu is rendered
    const menuElement = menu.shadowRoot?.querySelector('.menu');
    expect(menuElement).to.be.null;
  });

  it('shows menu when opened', async () => {
    const menu = await createCanvasMenu();

    // open the menu with messaging shortcuts
    menu.show(100, 100, { x: 50, y: 50 }, true, false, messageShortcuts);
    await menu.updateComplete;

    expect(menu.open).to.be.true;
    expect(menu.x).to.equal(100);
    expect(menu.y).to.equal(100);

    // verify menu is rendered
    const menuElement = menu.shadowRoot?.querySelector('.menu');
    expect(menuElement).to.not.be.null;

    await assertScreenshot('canvas-menu/open', getClip(menu));
  });

  it('shows messaging shortcuts for messaging flows', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, messageShortcuts);
    await menu.updateComplete;

    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    expect(menuItems?.length).to.equal(4);

    const titles = Array.from(menuItems || []).map(
      (item) => item.querySelector('.menu-item-title')?.textContent
    );
    expect(titles).to.deep.equal([
      'Send Message',
      'Wait for Response',
      'Add Other',
      'Add Sticky Note'
    ]);
  });

  it('shows voice shortcuts for voice flows', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, voiceShortcuts);
    await menu.updateComplete;

    const titles = Array.from(
      menu.shadowRoot?.querySelectorAll('.menu-item-title') || []
    ).map((item) => item.textContent);
    expect(titles).to.deep.equal([
      'Say Message',
      'Wait for Menu',
      'Add Other',
      'Add Sticky Note'
    ]);
  });

  it('shows background shortcuts for background flows', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, backgroundShortcuts);
    await menu.updateComplete;

    const titles = Array.from(
      menu.shadowRoot?.querySelectorAll('.menu-item-title') || []
    ).map((item) => item.textContent);
    expect(titles).to.deep.equal([
      'Update Contact',
      'Add Other',
      'Add Sticky Note'
    ]);
  });

  it('closes when close() is called', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, messageShortcuts);
    await menu.updateComplete;

    expect(menu.open).to.be.true;

    menu.close();
    await menu.updateComplete;

    expect(menu.open).to.be.false;
  });

  it('fires selection event when menu item is clicked', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, messageShortcuts);
    await menu.updateComplete;

    let selectionFired = false;
    let selectionDetail = null;

    menu.addEventListener('temba-selection', (event: any) => {
      selectionFired = true;
      selectionDetail = event.detail;
    });

    // click on sticky note option (the fourth item)
    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    const stickyItem = menuItems?.[3] as HTMLElement;
    stickyItem.click();
    await menu.updateComplete;

    expect(selectionFired).to.be.true;
    expect(selectionDetail).to.deep.equal({
      action: 'sticky',
      position: { x: 50, y: 50 }
    });
    expect(menu.open).to.be.false;
  });

  it('fires shortcut selection carrying the shortcut type', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, voiceShortcuts);
    await menu.updateComplete;

    let selectionDetail: any = null;
    menu.addEventListener('temba-selection', (event: any) => {
      selectionDetail = event.detail;
    });

    const firstShortcut = menu.shadowRoot?.querySelectorAll(
      '.menu-item'
    )?.[0] as HTMLElement;
    firstShortcut.click();
    await menu.updateComplete;

    expect(selectionDetail).to.deep.equal({
      action: 'say_msg',
      position: { x: 50, y: 50 }
    });
  });

  it('shows reflow option when showReflow is true', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, true, messageShortcuts);
    await menu.updateComplete;

    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    expect(menuItems?.length).to.equal(5);

    const titles = Array.from(menuItems || []).map(
      (item) => item.querySelector('.menu-item-title')?.textContent
    );
    expect(titles).to.deep.equal([
      'Send Message',
      'Wait for Response',
      'Add Other',
      'Add Sticky Note',
      'Reflow'
    ]);
  });

  it('fires reflow selection event when reflow is clicked', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, true, messageShortcuts);
    await menu.updateComplete;

    let selectionDetail = null;
    menu.addEventListener('temba-selection', (event: any) => {
      selectionDetail = event.detail;
    });

    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    const reflowItem = menuItems?.[4] as HTMLElement;
    reflowItem.click();
    await menu.updateComplete;

    expect(selectionDetail).to.deep.equal({
      action: 'reflow',
      position: { x: 50, y: 50 }
    });
    expect(menu.open).to.be.false;
  });

  it('hides reflow option by default', async () => {
    const menu = await createCanvasMenu();
    menu.show(100, 100, { x: 50, y: 50 }, true, false, messageShortcuts);
    await menu.updateComplete;

    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    expect(menuItems?.length).to.equal(4);

    const titles = Array.from(menuItems || []).map(
      (item) => item.querySelector('.menu-item-title')?.textContent
    );
    expect(titles).to.not.include('Reflow');
  });

  it('adjusts position to stay within viewport bounds', async () => {
    const menu = await createCanvasMenu();

    // open menu at position that would go off screen
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 10; // matches the margin in CanvasMenu

    // position that would go off the right and bottom edges
    menu.show(
      viewportWidth - 50,
      viewportHeight - 50,
      { x: 100, y: 100 },
      true,
      false,
      messageShortcuts
    );
    await menu.updateComplete;

    // wait for position adjustment
    await new Promise((resolve) => setTimeout(resolve, 100));
    await menu.updateComplete;

    const menuElement = menu.shadowRoot?.querySelector('.menu') as HTMLElement;
    expect(menuElement).to.not.be.null;

    const menuRect = menuElement.getBoundingClientRect();

    // verify menu stays within viewport with margin
    expect(menuRect.right).to.be.at.most(viewportWidth - margin);
    expect(menuRect.bottom).to.be.at.most(viewportHeight - margin);

    // verify click position is preserved (not adjusted)
    let selectionFired = false;
    let selectionDetail = null;

    menu.addEventListener('temba-selection', (event: any) => {
      selectionFired = true;
      selectionDetail = event.detail;
    });

    const menuItems = menu.shadowRoot?.querySelectorAll('.menu-item');
    const sendMsgItem = menuItems?.[0] as HTMLElement;
    sendMsgItem.click();
    await menu.updateComplete;

    expect(selectionFired).to.be.true;
    // click position should remain unchanged
    expect(selectionDetail.position).to.deep.equal({ x: 100, y: 100 });
  });
});
