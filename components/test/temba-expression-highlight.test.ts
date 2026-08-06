import { fixture, assert } from '@open-wc/testing';
import { ExpressionHighlight } from '../src/display/ExpressionHighlight';
import { assertScreenshot, getClip } from './utils.test';

const createHighlight = async (text: string) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 400px; padding: 10px;');
  return (await fixture(
    `<temba-expression-highlight>${text}</temba-expression-highlight>`,
    { parentNode }
  )) as ExpressionHighlight;
};

describe('temba-expression-highlight', () => {
  it('can be created', async () => {
    const el = await createHighlight('Hello world');
    assert.instanceOf(el, ExpressionHighlight);
  });

  it('highlights identifier expressions', async () => {
    const el = await createHighlight('Hi there @contact.name, welcome!');
    assert.instanceOf(el, ExpressionHighlight);
    await assertScreenshot('expression-highlight/identifier', getClip(el));
  });

  it('highlights parenthesized expressions', async () => {
    const el = await createHighlight(
      'Hi @(contact.first_name)! You have @(results.count) items.'
    );
    assert.instanceOf(el, ExpressionHighlight);
    await assertScreenshot('expression-highlight/parenthesized', getClip(el));
  });

  it('highlights function calls', async () => {
    const el = await createHighlight(
      'Today is @(format_date(now(), "YYYY-MM-DD"))'
    );
    assert.instanceOf(el, ExpressionHighlight);
    await assertScreenshot('expression-highlight/function', getClip(el));
  });

  it('renders plain text without expressions', async () => {
    const el = await createHighlight('Just plain text here');
    assert.instanceOf(el, ExpressionHighlight);
    await assertScreenshot('expression-highlight/plain', getClip(el));
  });
});
