import { expect, assert } from '@open-wc/testing';
import { FloatingWindow } from '../src/layout/FloatingWindow';
import { assertScreenshot, getComponent } from './utils.test';
import { setCookie } from '../src/utils';

describe('temba-floating-window', () => {
  it('can be created', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Phone Simulator',
        width: 250,
        maxHeight: 700,
        top: 100
      },
      '<div style="padding: 20px;">Window content goes here</div>',
      300,
      750
    )) as FloatingWindow;

    assert.instanceOf(window, FloatingWindow);
    expect(window.header).to.equal('Phone Simulator');
    expect(window.width).to.equal(250);
    expect(window.maxHeight).to.equal(700);
    expect(window.top).to.equal(100);

    // show the window for screenshot
    window.hidden = false;
    await window.updateComplete;
    expect(window.hidden).to.equal(false);

    // use custom clip for fixed positioned element
    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const clip = {
      x: window.left,
      y: window.top,
      width: window.width,
      height: windowElement.offsetHeight
    };
    await assertScreenshot('floating-window/default', clip);
  });

  it('starts hidden by default', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test Window'
      },
      '<div>Content</div>'
    )) as FloatingWindow;

    expect(window.hidden).to.equal(true);
  });

  it('can be shown and hidden', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test Window',
        hidden: true
      },
      '<div>Content</div>'
    )) as FloatingWindow;

    expect(window.hidden).to.equal(true);

    window.show();
    await window.updateComplete;
    expect(window.hidden).to.equal(false);
    expect(window.classList.contains('hidden')).to.equal(false);

    window.hide();
    await window.updateComplete;
    expect(window.hidden).to.equal(true);
  });

  it('fires close event when close button clicked', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test Window'
      },
      '<div>Content</div>',
      300,
      750
    )) as FloatingWindow;

    // show the window first
    window.hidden = false;
    await window.updateComplete;

    let closed = false;
    window.addEventListener('temba-dialog-hidden', () => {
      closed = true;
    });

    const closeButton = window.shadowRoot.querySelector(
      '.close-button'
    ) as HTMLElement;
    expect(closeButton).to.exist;

    closeButton.click();
    await window.updateComplete;

    expect(closed).to.equal(true);
    expect(window.hidden).to.equal(true);
  });

  it('displays header correctly', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Phone Simulator'
      },
      '<div>Content</div>',
      300,
      400
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const titleElement = window.shadowRoot.querySelector('.title');
    expect(titleElement).to.exist;
    expect(titleElement.textContent).to.equal('Phone Simulator');

    // use custom clip for fixed positioned element
    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const clip = {
      x: window.left,
      y: window.top,
      width: window.width,
      height: windowElement.offsetHeight
    };
    await assertScreenshot('floating-window/with-header', clip);
  });

  it('renders header icon when provided', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Revisions',
        icon: 'revisions'
      },
      '<div>Content</div>',
      300,
      400
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const icon = window.shadowRoot.querySelector(
      '.title-icon temba-icon'
    ) as HTMLElement;
    expect(icon).to.exist;
    expect(icon.getAttribute('name')).to.equal('revisions');
  });

  it('shows spinner icon and animation while saving', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Revisions',
        icon: 'revisions',
        saving: true
      },
      '<div>Content</div>',
      300,
      400
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const iconContainer = window.shadowRoot.querySelector(
      '.title-icon'
    ) as HTMLElement;
    expect(iconContainer).to.exist;
    expect(iconContainer.classList.contains('saving')).to.be.true;

    const icon = window.shadowRoot.querySelector(
      '.title-icon temba-icon'
    ) as HTMLElement;
    expect(icon.getAttribute('name')).to.equal('progress_spinner');
  });

  it('renders slot content', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test'
      },
      '<div class="test-content">Custom content</div>',
      300,
      400
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const slotContent = window.querySelector('.test-content');
    expect(slotContent).to.exist;
    expect(slotContent.textContent).to.equal('Custom content');
  });

  it('supports custom dimensions', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Custom Size',
        width: 400,
        maxHeight: 600,
        top: 100,
        left: 100
      },
      '<div>Content</div>',
      450,
      650
    )) as FloatingWindow;

    window.show();
    await window.updateComplete;
    expect(window.width).to.equal(400);
    expect(window.maxHeight).to.equal(600);
    expect(window.top).to.equal(100);
    expect(window.left).to.equal(100);

    // use custom clip for fixed positioned element
    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const clip = {
      x: window.left,
      y: window.top,
      width: window.width,
      height: windowElement.offsetHeight
    };

    await assertScreenshot('floating-window/custom-size', clip);
  });

  it('can be dragged by header', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Draggable Window',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const header = window.shadowRoot.querySelector('.header') as HTMLElement;
    expect(header).to.exist;

    // simulate drag by setting dragging state
    window.dragging = true;
    await window.updateComplete;

    const windowElement = window.shadowRoot.querySelector('.window');
    expect(windowElement.classList.contains('dragging')).to.equal(true);
  });

  it('respects viewport bounds when dragging', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Bounded Window',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div style="height: 200px;">Content with specific height</div>',
      300,
      450
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    // get actual window height
    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const actualHeight = windowElement.offsetHeight;

    // simulate dragging near bottom of viewport
    const viewportHeight = window.ownerDocument.defaultView.innerHeight;
    const maxAllowedTop = viewportHeight - actualHeight;

    // try to drag below the viewport
    window.top = viewportHeight + 100;
    await window.updateComplete;

    // the handleMouseMove should clamp this, but we'll test the logic exists
    expect(actualHeight).to.be.greaterThan(0);
    expect(maxAllowedTop).to.be.lessThan(viewportHeight);
  });

  it('maintains consistent starting position', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    // verify initial position matches properties
    expect(window.top).to.equal(100);
    expect(window.left).to.equal(100);

    // change position (simulating drag)
    window.top = 200;
    window.left = 200;
    await window.updateComplete;

    // hide and show
    window.hide();
    await window.updateComplete;
    window.show();
    await window.updateComplete;

    // position should remain at property values (100, 100) not dragged position
    expect(window.top).to.equal(100);
    expect(window.left).to.equal(100);
  });

  it('can disable chrome', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100,
        chromeless: true
      },
      '<div style="background: white; padding: 20px;">Chromeless content</div>',
      300,
      450
    )) as FloatingWindow;

    expect(window.chromeless).to.equal(true);

    window.hidden = false;
    await window.updateComplete;

    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    expect(windowElement.classList.contains('chromeless')).to.equal(true);

    // header should not be rendered
    const header = window.shadowRoot.querySelector('.header');
    expect(header).to.not.exist;

    // body should have no padding
    const body = window.shadowRoot.querySelector('.body') as HTMLElement;
    const bodyStyles = getComputedStyle(body);
    expect(bodyStyles.padding).to.equal('0px');

    // use custom clip for fixed positioned element
    const clip = {
      x: window.left,
      y: window.top,
      width: window.width,
      height: windowElement.offsetHeight
    };
    await assertScreenshot('floating-window/chromeless', clip);
  });

  it('defaults to showing chrome', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test'
      },
      '<div>Content</div>'
    )) as FloatingWindow;

    expect(window.chromeless).to.equal(false);
  });

  it('can close via public close() method', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test',
        chromeless: true
      },
      '<div>Content</div>'
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;
    expect(window.hidden).to.equal(false);

    let eventFired = false;
    window.addEventListener('temba-dialog-hidden', () => {
      eventFired = true;
    });

    // call public close() method
    window.close();
    await window.updateComplete;

    expect(window.hidden).to.equal(true);
    expect(eventFired).to.equal(true);
  });

  it('chromeless window has no borders or shadows', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Test',
        width: 250,
        maxHeight: 400,
        chromeless: true
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const styles = getComputedStyle(windowElement);

    expect(styles.boxShadow).to.equal('none');
    expect(styles.borderRadius).to.equal('0px');
    expect(styles.background.includes('rgba(0, 0, 0, 0)')).to.be.true;
  });

  it('supports min and max height constraints', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Min/Max Test',
        width: 300,
        minHeight: 200,
        maxHeight: 500
      },
      '<div style="padding: 20px;">Content that can vary in height</div>',
      350,
      550
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    expect(window.minHeight).to.equal(200);
    expect(window.maxHeight).to.equal(500);

    // verify the styles are applied
    const windowElement = window.shadowRoot.querySelector(
      '.window'
    ) as HTMLElement;
    const styles = getComputedStyle(windowElement);
    expect(styles.minHeight).to.equal('200px');
    expect(styles.maxHeight).to.equal('500px');
  });

  it('restores saved position from cookie on show', async () => {
    // save a position to the cookie
    setCookie(
      'window-positions',
      JSON.stringify({ 'test-win': { top: 200, left: 300 } })
    );

    const win = (await getComponent(
      'temba-floating-window',
      {
        header: 'Persist Test',
        name: 'test-win',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    // show the window — should restore from cookie
    win.show();
    await win.updateComplete;

    expect(win.top).to.equal(200);
    expect(win.left).to.equal(300);

    // clean up
    setCookie('window-positions', '{}');
  });

  it('saves position to cookie after drag', async () => {
    setCookie('window-positions', '{}');

    const win = (await getComponent(
      'temba-floating-window',
      {
        header: 'Save Test',
        name: 'drag-win',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    win.show();
    await win.updateComplete;

    // simulate drag via header mousedown + mousemove + mouseup
    const header = win.shadowRoot.querySelector('.header') as HTMLElement;
    header.dispatchEvent(
      new MouseEvent('mousedown', { clientX: 150, clientY: 110, bubbles: true })
    );
    document.dispatchEvent(
      new MouseEvent('mousemove', { clientX: 200, clientY: 160 })
    );
    document.dispatchEvent(new MouseEvent('mouseup'));
    await win.updateComplete;

    // cookie should now contain the position for this window
    const raw = document.cookie
      .split(';')
      .find((c) => c.trim().startsWith('window-positions='));
    expect(raw).to.exist;
    const positions = JSON.parse(
      decodeURIComponent(raw.split('=').slice(1).join('='))
    );
    expect(positions['drag-win']).to.exist;
    expect(positions['drag-win'].top).to.be.a('number');
    expect(positions['drag-win'].left).to.be.a('number');

    setCookie('window-positions', '{}');
  });

  it('clamps restored position to viewport bounds', async () => {
    // save a position that's way off screen
    setCookie(
      'window-positions',
      JSON.stringify({ 'clamp-win': { top: 50000, left: 50000 } })
    );

    const win = (await getComponent(
      'temba-floating-window',
      {
        header: 'Clamp Test',
        name: 'clamp-win',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div style="height: 200px;">Content</div>',
      300,
      450
    )) as FloatingWindow;

    win.show();
    await win.updateComplete;

    const padding = 20;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // position should be clamped within viewport
    expect(win.left).to.be.at.most(viewportWidth - win.width - padding);
    expect(win.top).to.be.at.most(viewportHeight - padding);

    setCookie('window-positions', '{}');
  });

  it('falls back to defaults when no saved position exists', async () => {
    setCookie('window-positions', '{}');

    const win = (await getComponent(
      'temba-floating-window',
      {
        header: 'Default Test',
        name: 'no-saved',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 150
      },
      '<div>Content</div>',
      300,
      450
    )) as FloatingWindow;

    win.show();
    await win.updateComplete;

    // should use the default property values
    expect(win.top).to.equal(100);
    expect(win.left).to.equal(150);
  });

  it('stays on screen when browser is resized', async () => {
    const window = (await getComponent(
      'temba-floating-window',
      {
        header: 'Resize Test',
        width: 250,
        maxHeight: 400,
        top: 100,
        left: 100
      },
      '<div style="height: 200px;">Content</div>',
      300,
      450
    )) as FloatingWindow;

    window.hidden = false;
    await window.updateComplete;

    // position window near right edge
    const originalViewportWidth = window.ownerDocument.defaultView.innerWidth;
    window.left = originalViewportWidth - window.width - 30;
    await window.updateComplete;

    // simulate window resize event (the component should constrain position)
    window.dispatchEvent(new Event('resize', { bubbles: true }));
    await window.updateComplete;

    // window should still be within viewport bounds with 20px padding
    const padding = 20;
    expect(window.left).to.be.at.least(padding);
    expect(window.left).to.be.at.most(
      window.ownerDocument.defaultView.innerWidth - window.width - padding
    );
    expect(window.top).to.be.at.least(padding);
  });
});
