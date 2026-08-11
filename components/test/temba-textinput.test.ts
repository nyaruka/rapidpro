import { fixture, expect, assert } from '@open-wc/testing';
import { TextInput } from '../src/form/TextInput';
import { assertScreenshot, getAttributes, getClip } from './utils.test';

export const getInputHTML = (attrs: any = { value: 'hello world' }) => {
  return `<temba-textinput ${getAttributes(attrs)}></temba-textinput>`;
};

export const createInput = async (def: string) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 250px;');
  const input: TextInput = await fixture(def, { parentNode });
  return input;
};

describe('temba-textinput', () => {
  it('can be created', async () => {
    const input: TextInput = await createInput(getInputHTML());
    assert.instanceOf(input, TextInput);
    await assertScreenshot('textinput/input', getClip(input));
  });

  it('shows placeholder', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ placeholder: 'Enter some text' })
    );

    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;

    expect(widget.placeholder).to.equal('Enter some text');
    await assertScreenshot('textinput/input-placeholder', getClip(input));
  });

  it('should focus inputs on click', async () => {
    const input: TextInput = await createInput(getInputHTML());
    await click('temba-textinput');
    await assertScreenshot('textinput/input-focused', getClip(input));
  });

  it('should render textarea', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world', textarea: true })
    );
    assert.instanceOf(input, TextInput);
    await assertScreenshot('textinput/textarea', getClip(input));
  });

  it('should focus textarea on click', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world', textarea: true })
    );
    await click('temba-textinput');
    await assertScreenshot('textinput/textarea-focused', getClip(input));
  });

  it('takes internal input changes', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world' })
    );

    // trigger a change on our internal widget
    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;
    expect(widget.tagName).to.equal('INPUT');
    expect(widget.disabled).to.equal(false);

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('to the ');

    // should be reflected on our main input
    expect(input.value).to.equal('hello to the world');
  });

  it('does not take internal input changes for disabled', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world', disabled: true })
    );

    // trigger a change on our internal widget
    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;
    expect(widget.tagName).to.equal('INPUT');
    expect(widget.disabled).to.equal(true);

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('to the ');

    // should be reflected on our main input
    expect(input.value).to.equal('hello world');
    await assertScreenshot('textinput/input-disabled', getClip(input));
  });

  it('takes internal textarea changes', async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world', textarea: true })
    );

    // trigger a change on our internal widget
    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;
    expect(widget.tagName).to.equal('TEXTAREA');
    expect(widget.disabled).to.equal(false);

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('to the ');

    // should be reflected on our main input
    expect(input.value).to.equal('hello to the world');
  });

  it('does not take internal textarea changes for disabled', async () => {
    const input: TextInput = await fixture(
      getInputHTML({ value: 'hello world', textarea: true, disabled: true })
    );

    // trigger a change on our internal widget
    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;
    expect(widget.tagName).to.equal('TEXTAREA');
    expect(widget.disabled).to.equal(true);

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('to the ');

    // should be reflected on our main input
    expect(input.value).to.equal('hello world');
  });

  it("doesn't advance cursor on GSM character replacement", async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world', textarea: true, gsm: true })
    );
    input.value = 'Let’s try some text with a funny tick.';

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('replaced ');

    expect(input.value).to.equal(
      "Let's try some text with a funny replaced tick."
    );
  });

  it("doesn't move cursor to the end on insert in input", async () => {
    const input: TextInput = await createInput(
      getInputHTML({ value: 'hello world' })
    );

    // focus our widget, move back a few spots and insert some text
    await click('temba-textinput');
    await pressKey('ArrowLeft', 5);
    await type('sad, sad ');

    expect(input.value).to.equal('hello sad, sad world');
    await assertScreenshot('textinput/input-inserted', getClip(input));
  });

  it('shows form attributes', async () => {
    const input: TextInput = await createInput(
      getInputHTML({
        name: 'message',
        value: 'hello world',
        label: 'Your Message',
        help_text: 'Enter your message here'
      })
    );
    await assertScreenshot('textinput/input-form', getClip(input));
  });

  it('updates input value', async () => {
    const input: TextInput = await createInput(
      getInputHTML({
        value: 'hello world'
      })
    );

    input.value = 'Updated by attribute change';
    const widget = input.shadowRoot.querySelector(
      '.textinput'
    ) as HTMLInputElement;

    await assertScreenshot('textinput/input-updated', getClip(input));
    expect(widget.value).to.equal('Updated by attribute change');
  });

  it('renders suffix content inside the chrome at the right edge', async () => {
    const input: TextInput = await createInput(
      `<temba-textinput value="hello world">
        <div slot="suffix" style="padding: 2px 6px">On</div>
      </temba-textinput>`
    );

    // the content lands in the input's own suffix slot
    const suffix = input.querySelector('[slot="suffix"]') as HTMLElement;
    const slot = suffix.assignedSlot as HTMLSlotElement;
    expect(slot.name).to.equal('suffix');
    expect(slot.getRootNode()).to.equal(input.shadowRoot);

    const container = input.shadowRoot.querySelector(
      '.input-container'
    ) as HTMLElement;
    const widget = input.shadowRoot.querySelector('.textinput') as HTMLElement;

    const chrome = container.getBoundingClientRect();
    const pill = suffix.getBoundingClientRect();
    const text = widget.getBoundingClientRect();

    // inside the chrome at its right edge, vertically centered
    expect(pill.right).to.be.at.most(chrome.right);
    expect(chrome.right - pill.right).to.be.at.most(12);
    expect(
      Math.abs(pill.top - chrome.top - (chrome.bottom - pill.bottom))
    ).to.be.at.most(2);

    // beside the text rather than over it
    expect(text.right).to.be.at.most(pill.left);

    await assertScreenshot('textinput/input-suffix', getClip(input));
  });

  it('initializes autogrow with content', async () => {
    const longText =
      'This is a very long text that should span multiple lines and cause the autogrow functionality to kick in and expand the textarea to accommodate all the content during initialization.';

    const input: TextInput = await createInput(
      getInputHTML({
        value: longText,
        textarea: true,
        autogrow: true
      })
    );

    // Wait for component to fully render
    await input.updateComplete;

    // Check that autogrow div has been updated with initial content
    const autogrowDiv = input.shadowRoot.querySelector(
      '.grow-wrap > div'
    ) as HTMLDivElement;
    expect(autogrowDiv).to.not.be.null;
    expect(autogrowDiv.innerText).to.include(longText);
    expect(autogrowDiv.innerText).to.include('\n'); // Should have the newline character added

    await assertScreenshot('textinput/autogrow-initial', getClip(input));
  });
});
