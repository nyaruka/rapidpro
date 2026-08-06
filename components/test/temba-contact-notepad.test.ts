import { expect, fixture, waitUntil } from '@open-wc/testing';
import { html } from 'lit';
import { ContactNotepad } from '../src/live/ContactNotepad';
import { resetContactWatches, updateContact } from '../src/live/ContactWatch';
import { setSocketProvider, SocketProvider } from '../src/live/SocketService';
import {
  getComponent,
  loadStore,
  mockGET,
  MockSocketProvider,
  waitForWatchedContact
} from './utils.test';

const TAG = 'temba-contact-notepad';

const OTHER_CONTACT = 'other-notepad-contact';

// a contact as the central watcher would hand it to us, carrying whatever
// note the server has for it
const contactWithNote = (text: string, uuid = 'notepad-contact'): any => ({
  uuid,
  name: 'Dave Matthews',
  urns: [],
  groups: [],
  fields: {},
  notes: [
    {
      text,
      created_on: '2026-01-06T12:00:00.000000Z',
      created_by: {
        email: 'eric@textit.com',
        first_name: 'Eric',
        last_name: 'Newcomer'
      }
    }
  ]
});

const getNotepad = async (attrs: any = {}) => {
  const notepad = (await getComponent(TAG, attrs, '', 400)) as ContactNotepad;
  await waitUntil(() => !!notepad.data);
  await notepad.updateComplete;
  return notepad;
};

const getTextarea = (notepad: ContactNotepad) =>
  notepad.shadowRoot.querySelector('.notepad') as HTMLTextAreaElement;

// the note is taken off a delivery from updated(), so the render that shows
// it is a follow-up pass
const settle = async (notepad: ContactNotepad) => {
  while (!(await notepad.updateComplete)) {
    // another update was scheduled while the last one ran
  }
};

describe('temba-contact-notepad', () => {
  let previousProvider: SocketProvider;

  beforeEach(() => {
    previousProvider = setSocketProvider(new MockSocketProvider());
    mockGET(
      /\/api\/v2\/contacts\.json\?.*uuid=notepad-contact/,
      '/test-assets/contacts/contact-notepad.json'
    );
    // the contact we switch to mid-edit
    mockGET(/\/api\/v2\/contacts\.json\?.*uuid=other-notepad-contact/, {
      next: null,
      previous: null,
      results: [contactWithNote('other note', OTHER_CONTACT)]
    });
  });

  afterEach(() => {
    resetContactWatches();
    setSocketProvider(previousProvider);
  });

  it('hugs the note text in autogrow mode', async () => {
    await loadStore();
    const notepad = await getNotepad({
      contact: 'notepad-contact',
      autogrow: true
    });

    const textarea = notepad.shadowRoot.querySelector(
      '.notepad'
    ) as HTMLTextAreaElement;

    // autosized to the content — no leftover empty height
    await waitUntil(
      () => Math.abs(textarea.clientHeight - textarea.scrollHeight) <= 2
    );

    // a one-line note stays a one-line notepad
    expect(textarea.clientHeight).to.be.lessThan(80);

    // growing the note grows the textarea to match
    const before = textarea.clientHeight;
    textarea.value = 'line\n'.repeat(10);
    textarea.dispatchEvent(new Event('input'));
    await notepad.updateComplete;

    await waitUntil(() => textarea.clientHeight > before + 50);
    expect(
      Math.abs(textarea.clientHeight - textarea.scrollHeight)
    ).to.be.lessThanOrEqual(2);
  });

  it('reports dirty state for a wrapping card', async () => {
    await loadStore();
    const notepad = await getNotepad({
      contact: 'notepad-contact',
      autogrow: true
    });

    const textarea = notepad.shadowRoot.querySelector(
      '.notepad'
    ) as HTMLTextAreaElement;

    const details = new Promise<CustomEvent>((resolve) => {
      notepad.addEventListener(
        'temba-details-changed',
        (event) => resolve(event as CustomEvent),
        { once: true }
      );
    });

    textarea.value = 'edited';
    textarea.dispatchEvent(new Event('input'));

    const event = await details;
    expect(event.detail.dirty).to.be.true;
  });

  it('keeps unsaved edits through a contact delivery', async () => {
    await loadStore();
    const notepad = await getNotepad({
      contact: 'notepad-contact',
      autogrow: true
    });
    await waitForWatchedContact('notepad-contact');

    const textarea = getTextarea(notepad);

    textarea.value = 'unsaved edit';
    textarea.dispatchEvent(new Event('input'));
    await settle(notepad);
    expect(notepad.dirty).to.be.true;

    // the watcher re-delivers the whole contact on any activity, not just
    // note changes - it can't take the edit down with it
    updateContact('notepad-contact', contactWithNote('server note'));
    await settle(notepad);

    expect(notepad.dirty).to.be.true;
    expect(textarea.value).to.equal('unsaved edit');

    // once the edit is no longer pending, deliveries land as usual
    notepad.markClean();
    updateContact('notepad-contact', contactWithNote('newer note'));
    await settle(notepad);

    expect(notepad.note.text).to.equal('newer note');
    expect(textarea.value).to.equal('newer note');

    // an abandoned edit comes back off even when the delivery carries the
    // same note it was typed over - the textarea is what has to end up right,
    // not just the note we derived
    textarea.value = 'abandoned edit';
    textarea.dispatchEvent(new Event('input'));
    await settle(notepad);
    notepad.markClean();

    updateContact('notepad-contact', contactWithNote('newer note'));
    await settle(notepad);

    expect(textarea.value).to.equal('newer note');
  });

  it('drops an unsaved edit when the contact switches', async () => {
    await loadStore();
    const notepad = await getNotepad({
      contact: 'notepad-contact',
      autogrow: true
    });
    await waitForWatchedContact('notepad-contact');

    const textarea = getTextarea(notepad);
    textarea.value = 'unsaved edit';
    textarea.dispatchEvent(new Event('input'));
    await settle(notepad);
    expect(notepad.dirty).to.be.true;

    // the notepad is reused across contacts (a ticket page swaps the contact
    // under it), and an edit only belongs to the contact it was typed
    // against - it goes with the one we left rather than being held for a
    // delivery it was never meant for
    notepad.contact = OTHER_CONTACT;
    await settle(notepad);
    await waitForWatchedContact(OTHER_CONTACT);
    updateContact(OTHER_CONTACT, contactWithNote('other note', OTHER_CONTACT));
    await settle(notepad);

    expect(notepad.dirty).to.be.false;
    expect(notepad.note.text).to.equal('other note');
    expect(getTextarea(notepad).value).to.equal('other note');
  });

  it('fills a bounded pane without overflowing it', async () => {
    // tab-mode arrangement: a plain bleed card of fixed height with the
    // notepad inside — the note surface fills the pane, toolbar at the
    // bottom, and nothing scrolls
    await loadStore();

    const parentNode = document.createElement('div');
    parentNode.setAttribute(
      'style',
      'width: 400px; height: 300px; display: flex;'
    );
    const card = (await fixture(
      html`
        <temba-card plain bleed>
          <temba-contact-notepad contact="notepad-contact" autogrow>
          </temba-contact-notepad>
        </temba-card>
      `,
      { parentNode }
    )) as HTMLElement;

    const notepad = card.querySelector(
      'temba-contact-notepad'
    ) as ContactNotepad;
    await waitUntil(() => !!notepad.data);
    await notepad.updateComplete;

    const content = card.shadowRoot.querySelector('.content') as HTMLElement;
    const toolbar = notepad.shadowRoot.querySelector('.toolbar') as HTMLElement;

    // give the resize-driven autosize a beat, then check for overflow
    await waitUntil(
      () => content.scrollHeight <= content.clientHeight + 1,
      'tab pane overflowed'
    );

    // the toolbar sits at the bottom of the pane
    const cardRect = card.getBoundingClientRect();
    const toolbarRect = toolbar.getBoundingClientRect();
    expect(Math.abs(cardRect.bottom - toolbarRect.bottom)).to.be.lessThan(4);
  });

  it('re-autosizes when its width changes', async () => {
    await loadStore();
    const notepad = await getNotepad({
      contact: 'notepad-contact',
      autogrow: true
    });

    const textarea = notepad.shadowRoot.querySelector(
      '.notepad'
    ) as HTMLTextAreaElement;

    // a single long line that wraps more as the notepad narrows
    textarea.value = 'wrap '.repeat(60);
    textarea.dispatchEvent(new Event('input'));
    await waitUntil(
      () => Math.abs(textarea.clientHeight - textarea.scrollHeight) <= 2
    );
    const wideHeight = textarea.clientHeight;

    // squeeze the notepad — the text rewraps and needs more height
    (notepad.parentElement as HTMLElement).style.width = '200px';
    await waitUntil(() => textarea.clientHeight > wideHeight + 20);
    expect(
      Math.abs(textarea.clientHeight - textarea.scrollHeight)
    ).to.be.lessThanOrEqual(2);
  });
});
