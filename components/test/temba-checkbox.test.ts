import { html, fixture, expect } from '@open-wc/testing';
import { Checkbox } from '../src/form/Checkbox';
import { Icon } from '../src/Icons';
import { assertScreenshot, getClip, getComponent } from './utils.test';

const getCheckbox = async (props: any) => {
  return (await getComponent('temba-checkbox', props)) as Checkbox;
};

describe('temba-checkbox', () => {
  it('renders default checkbox', async () => {
    const el = await getCheckbox({
      label: 'My Checkbox'
    });

    expect(el.label).to.equal('My Checkbox');
    await assertScreenshot('checkbox/default', getClip(el));
  });

  it('can select by clicking on the label', async () => {
    const el: Checkbox = await getCheckbox({
      label: 'My Checkbox',
      animatechange: false
    });

    (el.shadowRoot.querySelector('.checkbox-label') as HTMLDivElement).click();
    expect(el.checked).to.equal(true);
    await assertScreenshot('checkbox/checked', getClip(el));
  });

  it('fires change event on click', async () => {
    // eslint-disable-next-line no-async-promise-executor
    return new Promise<void>(async (resolve) => {
      const checkbox = await getCheckbox({
        label: 'My Checkbox'
      });

      checkbox.addEventListener('change', () => {
        resolve();
      });

      click('temba-checkbox');
    });
  });

  it('checks via click method', async () => {
    const checkbox = await getCheckbox({
      label: 'My Checkbox'
    });
    checkbox.click();
    expect(checkbox.checked).to.equal(true);
  });

  it('has background hover effect when label is set', async () => {
    const el: Checkbox = await getCheckbox({
      label: 'My Label',
      name: 'My Checkbox'
    });

    expect(el.label).to.equal('My Label');
    //the ".wrapper.label" style results in the background hover effect
    const wrapperDivEl = el.shadowRoot.querySelector(
      'div.wrapper.label'
    ) as HTMLDivElement;
    expect(wrapperDivEl).to.not.equal(null);
    await assertScreenshot(
      'checkbox/checkbox-label-background-hover',
      getClip(el)
    );
  });

  //note: sometimes upstream logic sets an empty checkbox label to the name value,
  //but this is the expected behavior if the label value is still empty,
  //upon rendering the component
  it('has no background hover effect when label is empty', async () => {
    const el: Checkbox = await getCheckbox({
      name: 'My Checkbox'
    });

    expect(el.label).to.equal(undefined);
    //the ".wrapper.label" style results in the background hover effect
    const wrapperDivEl = el.shadowRoot.querySelector(
      'div.wrapper.label'
    ) as HTMLDivElement;
    expect(wrapperDivEl).to.equal(null);
    await assertScreenshot(
      'checkbox/checkbox-no-label-no-background-hover',
      getClip(el)
    );
  });

  it('has no background hover effect when label is whitespace', async () => {
    const el: Checkbox = await getCheckbox({
      name: 'My Checkbox',
      label: ''
    });

    expect(el.label).to.equal('');
    //the ".wrapper.label" style results in the background hover effect
    const wrapperDivEl = el.shadowRoot.querySelector(
      'div.wrapper.label'
    ) as HTMLDivElement;
    expect(wrapperDivEl).to.equal(null);
    await assertScreenshot(
      'checkbox/checkbox-whitespace-label-no-background-hover',
      getClip(el)
    );
  });

  it('submits as boolean without value', async () => {
    const form = (await fixture(html`
      <form>
        <temba-checkbox name="my-cb"></temba-checkbox>
      </form>
    `)) as HTMLFormElement;

    // if we didn't click it, it shouldn't be in the form data
    let data = new FormData(form);
    expect(data.get('my-cb')).to.equal(null);

    // click our checkbox
    const checkbox = form.querySelector('temba-checkbox') as Checkbox;
    await click('temba-checkbox');
    expect(checkbox.checked).to.equal(true);

    // clicking a non-value checkbox should set it to 1
    data = new FormData(form);
    expect(data.get('my-cb')).to.equal('1');
  });

  it('supports custom values', async () => {
    const form = (await fixture(html`
      <form>
        <temba-checkbox name="my-cb" value="3"></temba-checkbox>
      </form>
    `)) as HTMLFormElement;

    // if we didn't click it, it shouldn't be in the form data
    let data = new FormData(form);
    expect(data.get('my-cb')).to.equal(null);

    // click our checkbox
    const checkbox = form.querySelector('temba-checkbox') as Checkbox;
    await click('temba-checkbox');
    expect(checkbox.checked).to.equal(true);

    // clicking a non-value checkbox should set it to 1
    data = new FormData(form);
    expect(data.get('my-cb')).to.equal('3');
  });

  it('supports programmtically updated values', async () => {
    // start with empty value
    const form = (await fixture(html`
      <form>
        <temba-checkbox name="my-cb"></temba-checkbox>
      </form>
    `)) as HTMLFormElement;

    // update our value directly
    const checkbox = form.querySelector('temba-checkbox') as Checkbox;
    checkbox.value = '5';

    // we set a custom value, but we still aren't checked
    let data = new FormData(form);
    expect(data.get('my-cb')).to.equal(null);

    // click our checkbox
    await click('temba-checkbox');
    expect(checkbox.checked).to.equal(true);

    // clicking a non-value checkbox should set it to 1
    data = new FormData(form);
    expect(data.get('my-cb')).to.equal('5');
  });

  it('aligns help text with label when both are present', async () => {
    const el: Checkbox = (await getCheckbox({
      label: 'Checkbox with help',
      help_text: 'This help text should align with the label text'
    })) as unknown as Checkbox;

    expect(el.label).to.equal('Checkbox with help');
    expect(el.helpText).to.equal(
      'This help text should align with the label text'
    );

    // Verify help text element exists and has proper alignment styles
    const helpTextEl = el.shadowRoot.querySelector(
      '.checkbox-help-text'
    ) as HTMLElement;
    expect(helpTextEl).to.not.be.null;
    expect(helpTextEl.textContent.trim()).to.equal(
      'This help text should align with the label text'
    );

    await assertScreenshot('checkbox/checkbox-with-help-text', getClip(el));
  });

  it('ignores clicks and shows spinning arrows while busy', async () => {
    const el: Checkbox = await getCheckbox({
      label: 'My Checkbox',
      busy: true
    });

    // a busy checkbox must not toggle when clicked — the host owns the
    // in-flight change and clears busy when it resolves
    el.click();
    expect(el.checked).to.not.equal(true);

    // the glyph is swapped for a spinning progress icon
    const icon = el.shadowRoot.querySelector('temba-icon') as HTMLElement;
    expect(icon.getAttribute('name')).to.equal(Icon.progress_spinner);
    expect(icon.hasAttribute('spin')).to.equal(true);

    // clearing busy restores normal click-to-toggle behavior
    el.busy = false;
    await el.updateComplete;
    el.click();
    expect(el.checked).to.equal(true);
  });
});
