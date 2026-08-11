import { html, fixture, expect } from '@open-wc/testing';
import { TemplateEditor } from '../src/form/TemplateEditor';
import { TemplateResult } from 'lit';
import { assertScreenshot, getClip } from './utils.test';

const createTemplateEditor = async (def: TemplateResult) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 520px;');
  const templateEditor = await fixture<TemplateEditor>(def, { parentNode });

  await templateEditor.updateComplete;
  return templateEditor;
};

describe('TemplateEditor', () => {
  it('renders template content', async () => {
    const templateEditor = await createTemplateEditor(html`
      <temba-template-editor
        url="/static/api/templates.json"
        template="2b1cdee4-71b4-4c9a-805c-9bce6a2e7277"
      >
      </temba-template-editor>
    `);
    const clip = getClip(templateEditor);
    clip.height = 500;
    clip.bottom = clip.top + clip.height;
    await assertScreenshot('templates/default', clip);
  });

  it('renders an error message no language is found', async () => {
    const templateEditor = await createTemplateEditor(html`
      <temba-template-editor
        url="/static/api/templates.json"
        template="3b1cdee4-71b4-4c9a-805c-9bce6a2e7277"
      >
      </temba-template-editor>
    `);

    const clip = getClip(templateEditor);
    clip.height = 200;
    clip.bottom = clip.top + clip.height;

    await assertScreenshot('templates/unapproved', clip);

    const errorMessage = (
      templateEditor.shadowRoot.querySelector(
        '.error-message'
      ) as HTMLDivElement
    ).innerText;
    expect(errorMessage).to.equal(
      'This template currently has no approved translations.'
    );
  });

  it('passes session mode to variable completions', async () => {
    const templateEditor = await createTemplateEditor(html`
      <temba-template-editor session></temba-template-editor>
    `);

    templateEditor.translation = {
      locale: 'en',
      status: 'approved',
      channel: { uuid: 'chan-1', name: 'WhatsApp' },
      variables: [{ type: 'text' }],
      components: [
        {
          name: 'body',
          type: 'body',
          content: 'Hi {{1}}',
          variables: { '1': 0 }
        }
      ]
    } as any;
    templateEditor.currentVariables = [''];

    await templateEditor.updateComplete;

    const variableInput = templateEditor.shadowRoot.querySelector(
      'temba-completion.variable'
    ) as HTMLElement;
    expect(variableInput).to.exist;
    expect(variableInput.hasAttribute('session')).to.be.true;
  });
});
