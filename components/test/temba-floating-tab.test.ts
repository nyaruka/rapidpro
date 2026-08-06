import { expect, assert } from '@open-wc/testing';
import { FloatingTab } from '../src/display/FloatingTab';
import { assertScreenshot, getClip, getComponent } from './utils.test';

describe('temba-floating-tab', () => {
  it('can be created', async () => {
    const tab = (await getComponent('temba-floating-tab', {
      icon: 'phone',
      label: 'Phone Simulator',
      color: '#10b981'
    })) as FloatingTab;

    assert.instanceOf(tab, FloatingTab);
    expect(tab.icon).to.equal('phone');
    expect(tab.label).to.equal('Phone Simulator');
    expect(tab.color).to.equal('#10b981');
    expect(tab.hidden).to.equal(false);

    await assertScreenshot('floating-tab/default', getClip(tab));
  });

  it('can be hidden', async () => {
    const tab = (await getComponent('temba-floating-tab', {
      icon: 'phone',
      label: 'Phone Simulator',
      color: '#10b981',
      hidden: true
    })) as FloatingTab;

    expect(tab.hidden).to.equal(true);
    expect(tab.classList.contains('hidden')).to.equal(true);

    await assertScreenshot('floating-tab/hidden', getClip(tab));
  });

  it('shows label on hover', async () => {
    const tab = (await getComponent('temba-floating-tab', {
      icon: 'phone',
      label: 'Phone Simulator',
      color: '#6366f1'
    })) as FloatingTab;

    const tabElement = tab.shadowRoot.querySelector('.tab') as HTMLElement;
    expect(tabElement).to.exist;

    // simulate hover state
    const labelElement = tab.shadowRoot.querySelector('.label') as HTMLElement;
    expect(labelElement).to.exist;

    await assertScreenshot('floating-tab/hover', getClip(tab));
  });

  it('fires click event', async () => {
    const tab = (await getComponent('temba-floating-tab', {
      icon: 'clock',
      label: 'History',
      color: '#8b5cf6'
    })) as FloatingTab;

    let clicked = false;
    tab.addEventListener('temba-button-clicked', () => {
      clicked = true;
    });

    const tabElement = tab.shadowRoot.querySelector('.tab') as HTMLElement;
    tabElement.click();

    expect(clicked).to.equal(true);
  });

  it('supports different colors', async () => {
    const tab1 = (await getComponent('temba-floating-tab', {
      icon: 'phone',
      label: 'Phone',
      color: '#10b981',
      order: 1
    })) as FloatingTab;

    const tab2 = (await getComponent('temba-floating-tab', {
      icon: 'globe',
      label: 'Translation',
      color: '#6b7280',
      order: 2
    })) as FloatingTab;

    const tab3 = (await getComponent('temba-floating-tab', {
      icon: 'clock',
      label: 'History',
      color: '#8b5cf6',
      order: 3
    })) as FloatingTab;

    await assertScreenshot('floating-tab/green', getClip(tab1));
    await assertScreenshot('floating-tab/gray', getClip(tab2));
    await assertScreenshot('floating-tab/purple', getClip(tab3));
  });
});
