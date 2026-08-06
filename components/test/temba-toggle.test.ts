import { assert, expect, fixture } from '@open-wc/testing';
import { Toggle } from '../src/form/Toggle';
import { assertScreenshot, getClip, getComponent } from './utils.test';

const TAG = 'temba-toggle';

const getToggle = async (attrs: any = {}, width = 220): Promise<Toggle> =>
  (await getComponent(TAG, attrs, '', width)) as Toggle;

const wrapper = (toggle: Toggle): HTMLElement =>
  toggle.shadowRoot.querySelector('.wrapper');

describe(TAG, () => {
  it('can be created', async () => {
    const toggle = await getToggle({ label: 'Published' });

    assert.instanceOf(toggle, Toggle);
    expect(toggle.checked).to.be.false;
    expect(wrapper(toggle).classList.contains('on')).to.be.false;
    expect(
      toggle.shadowRoot.querySelector('.toggle-label').textContent.trim()
    ).to.equal('Published');
  });

  it('flips when clicked and says so', async () => {
    const toggle = await getToggle({ label: 'Published' });

    const changes: boolean[] = [];
    toggle.addEventListener('change', () => changes.push(toggle.checked));

    wrapper(toggle).click();
    await toggle.updateComplete;

    expect(toggle.checked).to.be.true;
    expect(wrapper(toggle).classList.contains('on')).to.be.true;
    expect(wrapper(toggle).getAttribute('aria-checked')).to.equal('true');

    wrapper(toggle).click();
    await toggle.updateComplete;

    expect(toggle.checked).to.be.false;
    expect(changes).to.deep.equal([true, false]);
  });

  it('flips from the keyboard', async () => {
    const toggle = await getToggle({ label: 'Published' });

    for (const key of [' ', 'Enter']) {
      const before = toggle.checked;
      wrapper(toggle).dispatchEvent(new KeyboardEvent('keydown', { key }));
      await toggle.updateComplete;
      expect(toggle.checked).to.equal(!before);
    }

    // anything else is left to the browser
    wrapper(toggle).dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    await toggle.updateComplete;
    expect(toggle.checked).to.be.false;
  });

  it('cannot be flipped while disabled', async () => {
    const toggle = await getToggle({ label: 'Published', disabled: true });

    wrapper(toggle).click();
    wrapper(toggle).dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }));
    await toggle.updateComplete;

    expect(toggle.checked).to.be.false;
    // and it's out of the tab order, so it can't be reached to be flipped either
    expect(wrapper(toggle).getAttribute('tabindex')).to.equal('-1');
  });

  it('posts a value only while it is on', async () => {
    const form = (await fixture(`
      <form>
        <${TAG} name="published" label="Published"></${TAG}>
      </form>
    `)) as HTMLFormElement;

    const toggle = form.querySelector(TAG) as Toggle;
    await toggle.updateComplete;

    expect(new FormData(form).get('published')).to.be.null;

    toggle.checked = true;
    await toggle.updateComplete;

    expect(new FormData(form).get('published')).to.equal('1');
  });

  it('renders both states (screenshot)', async () => {
    const toggles = (await fixture(`
      <div style="display:inline-flex; gap:1em; padding:0.5em; background:#fff">
        <${TAG} widget_only label="Draft"></${TAG}>
        <${TAG} widget_only label="Published" checked></${TAG}>
      </div>
    `)) as HTMLElement;

    for (const toggle of toggles.querySelectorAll(TAG)) {
      await (toggle as Toggle).updateComplete;
    }

    await assertScreenshot('toggle/states', getClip(toggles));
  });
});
