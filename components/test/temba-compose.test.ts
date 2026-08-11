import { assert, expect } from '@open-wc/testing';
import { Compose } from '../src/form/Compose';
import {
  assertScreenshot,
  getClip,
  getComponent,
  getValidAttachments,
  getValidText,
  updateComponent
} from './utils.test';
import { DEFAULT_MEDIA_ENDPOINT } from '../src/utils';
import { Attachment } from '../src/interfaces';

const TAG = 'temba-compose';
const getCompose = async (attrs: any = {}, width = 500, height = 500) => {
  const compose = (await getComponent(
    TAG,
    attrs,
    '',
    width,
    height,
    'display:flex;flex-direction:column;flex-grow:1;'
  )) as Compose;
  return compose;
};

const getInitialValue = (
  text?: string,
  attachments?: Attachment[],
  quick_replies?: []
): any => {
  const composeValue = {
    und: {
      text: text ? text : '',
      attachments: attachments ? attachments : [],
      quick_replies: quick_replies ? quick_replies : [],
      template: null,
      variables: []
    }
  };
  return composeValue;
};
const getComposeValue = (value: any): string => {
  return JSON.stringify(value);
};

// for a test width of 500, return a string that is 60+ chars with spaces
// to test that line breaks / word wrapping works as expected
const getValidText_Long_WithSpaces = () => {
  return 'bbbbbbbbbb bbbbbbbbbb bbbbbbbbbb bbbbbbbbbb bbbbbbbbbb bbbbbbbbbb bbbbbbbbbb ';
};

const getValidText_Long_WithNoSpaces = () => {
  return 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
};

const getValidText_Long_WithUrl = () => {
  return 'http://www.yourmomyourmomyourmomyourmomyourmomyourmomyourmomyourmomyourmomyourmomyourmom.com';
};

describe('temba-compose chatbox', () => {
  it('can be created', async () => {
    const compose: Compose = await getCompose();
    assert.instanceOf(compose, Compose);
    expect(compose.endpoint).equals(DEFAULT_MEDIA_ENDPOINT);
  });

  it('cannot be created with a different endpoint', async () => {
    const compose: Compose = await getCompose({
      endpoint: '/schmsgmedia/schmupload/'
    });
    assert.instanceOf(compose, Compose);
    expect(compose.endpoint).equals(DEFAULT_MEDIA_ENDPOINT);
  });

  it('no counter', async () => {
    const compose: Compose = await getCompose({
      chatbox: true
    });
    await assertScreenshot('compose/no-counter', getClip(compose));
  });

  it('initializes with text', async () => {
    const compose: Compose = await getCompose({
      counter: true
    });
    await updateComponent(compose, getValidText());
    await assertScreenshot('compose/intial-text', getClip(compose));
  });

  it('serializes', async () => {
    const initialValue = getInitialValue(getValidText());
    const composeValue = getComposeValue(initialValue);

    const compose: Compose = await getCompose({
      counter: true,
      value: composeValue
    });

    // deserialize
    expect(compose.currentText).to.equal(getValidText());
    expect(compose.currentAttachments).to.deep.equal([]);

    // serialize
    expect(compose.value).to.equal(composeValue);
  });

  // TODO: these are better suited for textinput tests
  it('wraps text and spaces', async () => {
    const compose: Compose = await getCompose({
      counter: true
    });
    await updateComponent(compose, getValidText_Long_WithSpaces());
    await assertScreenshot('compose/wraps-text-and-spaces', getClip(compose));
  });

  it('wraps text and no spaces', async () => {
    const compose: Compose = await getCompose({
      counter: true
    });
    await updateComponent(compose, getValidText_Long_WithNoSpaces());
    await assertScreenshot('compose/wraps-text-no-spaces', getClip(compose));
  });

  it('wraps with text and url', async () => {
    const compose: Compose = await getCompose({
      counter: true
    });
    await updateComponent(compose, getValidText_Long_WithUrl());
    await assertScreenshot('compose/wraps-text-and-url', getClip(compose));
  });

  it('keeps template variable session completion disabled by default', async () => {
    const compose: Compose = await getCompose({
      templates: true
    });

    const templateEditor = compose.shadowRoot.querySelector(
      'temba-template-editor'
    ) as HTMLElement;
    expect(templateEditor).to.not.be.null;
    expect(templateEditor.hasAttribute('session')).to.be.false;
  });

  it('enables template variable session completion with template-session attribute', async () => {
    const compose: Compose = await getCompose({
      templates: true,
      'template-session': true
    });

    const templateEditor = compose.shadowRoot.querySelector(
      'temba-template-editor'
    ) as HTMLElement;
    expect(templateEditor).to.not.be.null;
    expect(templateEditor.hasAttribute('session')).to.be.true;
  });
});

describe('temba-compose attachments', () => {
  it('supports attachments tab', async () => {
    const compose: Compose = await getCompose({
      attachments: true
    });
    await assertScreenshot('compose/attachments-tab', getClip(compose));
  });

  it('shows valid attachments', async () => {
    const compose: Compose = await getCompose({
      attachments: true
    });
    await updateComponent(compose, null, getValidAttachments());
    await assertScreenshot('compose/attachments-with-files', getClip(compose));
  });

  it('serializes attachments', async () => {
    const initialValue = getInitialValue(null, getValidAttachments());
    const composeValue = getComposeValue(initialValue);
    const compose: Compose = await getCompose({
      attachments: true,
      value: composeValue
    });
    // deserialize
    expect(compose.currentText).to.equal('');
    expect(compose.currentAttachments).to.deep.equal(getValidAttachments());
    // serialize
    expect(compose.value).to.equal(composeValue);
  });
});

describe('temba-compose broadcast edit', () => {
  it('initializes with languages and value like Django', async () => {
    // Simulate Django broadcast edit: value keyed by language iso
    const langValue = {
      eng: {
        text: 'Hello from broadcast',
        attachments: [],
        quick_replies: [{ text: 'Yes' }, 'No'],
        template: null,
        variables: []
      }
    };
    const languages = JSON.stringify([{ iso: 'eng', name: 'English' }]);

    const compose: Compose = await getCompose({
      counter: true,
      attachments: true,
      completion: true,
      quickreplies: true,
      templates: true,
      maxlength: 4096,
      languages: languages,
      value: JSON.stringify(langValue)
    });

    // Verify the compose initialized correctly
    expect(compose.currentLanguage).to.equal('eng');
    expect(compose.currentText).to.equal('Hello from broadcast');
    expect(compose.currentQuickReplies).to.deep.equal([
      { name: 'Yes', value: 'Yes' },
      { name: 'No', value: 'No' }
    ]);
    expect(JSON.parse(compose.value).eng.quick_replies).to.deep.equal([
      'Yes',
      'No'
    ]);

    // Verify the message editor exists in shadow DOM and has content
    const editor = compose.shadowRoot.querySelector('temba-message-editor');
    expect(editor).to.not.be.null;
    expect((editor as any).value).to.equal('Hello from broadcast');

    // Verify accordion sections are rendered
    const accordion = compose.shadowRoot.querySelector('temba-accordion');
    expect(accordion).to.not.be.null;
  });

  it('initializes with template value missing attachments and quick_replies', async () => {
    // Django may omit attachments/quick_replies when a template is set
    const langValue = {
      eng: {
        text: 'Hello',
        template: 'd6a73193-c31e-4943-bd2d-edf920fb82eb',
        variables: ['world']
      }
    };
    const languages = JSON.stringify([
      { iso: 'eng', name: 'English' },
      { iso: 'spa', name: 'Spanish' }
    ]);

    const compose: Compose = await getCompose({
      counter: true,
      attachments: true,
      completion: true,
      quickreplies: true,
      templates: true,
      maxlength: 4096,
      languages: languages,
      value: JSON.stringify(langValue)
    });

    expect(compose.currentLanguage).to.equal('eng');
    expect(compose.currentText).to.equal('Hello');
    expect(compose.currentAttachments).to.deep.equal([]);
    expect(compose.currentQuickReplies).to.deep.equal([]);

    // Verify the shadow DOM rendered (not empty)
    const editor = compose.shadowRoot.querySelector('temba-message-editor');
    expect(editor).to.not.be.null;
  });
});

describe('temba-compose enter key', () => {
  const getComposeWithText = async () => {
    const compose: Compose = await getCompose({
      quickreplies: true,
      chatbox: true,
      counter: true,
      value: getComposeValue(getInitialValue('hello there'))
    });
    return compose;
  };

  it('sends on Enter in the message editor', async () => {
    const compose = await getComposeWithText();
    let submitted = 0;
    compose.addEventListener('temba-submitted', () => {
      submitted++;
    });

    // click into the editor and press Enter
    await typeInto('temba-compose:temba-message-editor', '', false, false);
    await waitFor(100);
    await pressKey('Enter', 1);
    await waitFor(100);
    expect(submitted).to.equal(1);
  });

  it('adds a quick reply on Enter without sending', async () => {
    const compose = await getComposeWithText();
    let submitted = 0;
    compose.addEventListener('temba-submitted', () => {
      submitted++;
    });

    // expand the quick replies section
    const section = compose.shadowRoot.querySelector(
      'temba-accordion-section'
    ) as any;
    section.collapsed = false;
    await section.updateComplete;
    await compose.updateComplete;

    const select = compose.shadowRoot.querySelector(
      'temba-select.quick-replies'
    ) as any;

    await typeInto(
      'temba-compose:temba-select.quick-replies',
      'Maybe',
      false,
      false
    );
    await pressKey('Enter', 1);
    await waitFor(100);
    await compose.updateComplete;

    expect(select.values.length).to.equal(1);
    expect(select.values[0].value).to.equal('Maybe');
    expect(compose.currentQuickReplies).to.have.length(1);
    expect(submitted).to.equal(0);
  });
});

describe('temba-compose language visualization', () => {
  const getLangSelect = async (compose: Compose) => {
    const select = compose.shadowRoot.querySelector(
      'temba-select.language'
    ) as any;
    if (select) {
      await select.updateComplete;
    }
    return select;
  };

  it('pins base language first and sorts translated before missing', async () => {
    const langValue = {
      eng: { text: 'Hello', attachments: [], quick_replies: [] },
      fra: { text: 'Bonjour', attachments: [], quick_replies: [] }
    };
    const compose: Compose = await getCompose({
      languages: JSON.stringify([
        { iso: 'eng', name: 'English' },
        { iso: 'spa', name: 'Spanish' },
        { iso: 'fra', name: 'French' },
        { iso: 'deu', name: 'German' }
      ]),
      value: JSON.stringify(langValue)
    });

    const select = await getLangSelect(compose);
    const options = select.staticOptions;
    expect(options.map((o: any) => o.iso)).to.deep.equal([
      'eng',
      'fra',
      'spa',
      'deu'
    ]);
  });

  it('keeps base language first even when it has no content', async () => {
    const langValue = {
      fra: { text: 'Bonjour', attachments: [], quick_replies: [] }
    };
    const compose: Compose = await getCompose({
      languages: JSON.stringify([
        { iso: 'eng', name: 'English' },
        { iso: 'fra', name: 'French' }
      ]),
      value: JSON.stringify(langValue)
    });

    const select = await getLangSelect(compose);
    expect(select.staticOptions.map((o: any) => o.iso)).to.deep.equal([
      'eng',
      'fra'
    ]);
  });

  it('renders Original badge for the base language in the selected display', async () => {
    const compose: Compose = await getCompose({
      languages: JSON.stringify([
        { iso: 'eng', name: 'English' },
        { iso: 'spa', name: 'Spanish' }
      ]),
      value: JSON.stringify({
        eng: { text: 'Hello', attachments: [], quick_replies: [] }
      })
    });

    const select = await getLangSelect(compose);
    expect(select.shadowRoot.querySelector('.selected').textContent).to.include(
      'Original'
    );
  });

  it('reorders options when content is added to a previously missing language', async () => {
    const compose: Compose = await getCompose({
      languages: JSON.stringify([
        { iso: 'eng', name: 'English' },
        { iso: 'spa', name: 'Spanish' },
        { iso: 'deu', name: 'German' }
      ]),
      value: JSON.stringify({
        eng: { text: 'Hello', attachments: [], quick_replies: [] }
      })
    });

    let select = await getLangSelect(compose);
    expect(select.staticOptions.map((o: any) => o.iso)).to.deep.equal([
      'eng',
      'spa',
      'deu'
    ]);

    // Simulate the user adding a translation for German
    compose.langValues = {
      ...compose.langValues,
      deu: { text: 'Hallo', attachments: [], quick_replies: [] }
    };
    compose.currentLanguage = 'deu';
    compose.currentText = 'Hallo';
    await compose.updateComplete;

    select = await getLangSelect(compose);
    expect(select.staticOptions.map((o: any) => o.iso)).to.deep.equal([
      'eng',
      'deu',
      'spa'
    ]);
  });
});
