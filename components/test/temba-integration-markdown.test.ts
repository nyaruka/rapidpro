import { expect } from '@open-wc/testing';
import { assertScreenshot, getClip, getComponent } from './utils.test';
import { TextInput } from '../src/form/TextInput';

describe('FormElement markdown integration', () => {
  it('renders textinput with markdown errors', async () => {
    const el: TextInput = (await getComponent('temba-textinput', {
      name: 'my_textinput'
    })) as TextInput;

    el.errors = [
      'You must agree to the **terms and conditions** at [this link](https://example.com)',
      'This field *requires* a value'
    ];

    await el.updateComplete;

    // Check that errors are rendered with markdown directly in checkbox shadow root
    const errorElements = el.shadowRoot.querySelectorAll('.alert-error');
    expect(errorElements.length).to.equal(2);

    // First error should have bold text and link
    const firstError = errorElements[0];
    const boldElement = firstError.querySelector('strong');
    const linkElement = firstError.querySelector('a');
    expect(boldElement).to.not.be.null;
    expect(boldElement.textContent).to.equal('terms and conditions');
    expect(linkElement).to.not.be.null;
    expect(linkElement.getAttribute('href')).to.equal('https://example.com');

    // Second error should have italic text
    const secondError = errorElements[1];
    const italicElement = secondError.querySelector('em');
    expect(italicElement).to.not.be.null;
    expect(italicElement.textContent).to.equal('requires');

    await assertScreenshot(
      'integration/textinput-markdown-errors',
      getClip(el)
    );
  });
});
