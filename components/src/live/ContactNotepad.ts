import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { ContactStoreElement } from './ContactStoreElement';
import { getDisplayName } from './ContactChat';
import { ContactNote, CustomEventType } from '../interfaces';
import { designTokens } from '../styles/designTokens';

export class ContactNotepad extends ContactStoreElement {
  // notes have no contact events - an empty interest list still receives
  // eventless deliveries (initial values, refetches and page-local edits)
  protected watchTypes: string[] = [];

  @property({ type: Object, attribute: false })
  note: ContactNote;

  @property({ type: String })
  dirtyMessage =
    'You have unsaved changes to the contact notepad. Are you sure you want to contiunue?';

  // grow with the note instead of filling the parent and scrolling —
  // used when embedded in a card that must never scroll internally
  @property({ type: Boolean, reflect: true })
  autogrow = false;

  static get styles() {
    return css`
      ${designTokens}

      :host {
        height: 100%;
        display: flex;
        margin-top: var(--gap);
      }

      .wrapper {
        flex-grow: 1;
        --color-widget-bg: transparent;
        --color-widget-bg-focused: transparent;
        outline: none;
        display: flex;
        flex-direction: column;
        background: var(--surface-note);
        border: 1px solid var(--border-note);
        border-radius: var(--r-sm);
        box-shadow: var(--shadow-2);
        overflow: hidden;
      }

      .notepad {
        flex-grow: 1;
        padding: 1.25rem;
        overflow-y: auto;
        background: transparent;
        border: none;
        outline: none;
        resize: none;
        font-family: monospace;
      }

      .notepad:focus {
        outline: none;
      }

      /* flex-grow only matters in a height-bounded flex parent (the tab
         pane): the textarea stretches to fill the note surface, pinning
         the attribution toolbar to the bottom. In the card column the
         parent is a plain block, so the notepad still hugs its text. */
      :host([autogrow]) {
        height: auto;
        margin-top: 0;
        flex-grow: 1;
        /* in a height-bounded flex parent (tab pane) the autosize can
           measure while flex-stretched and overshoot — allow flex to
           shrink us back so the toolbar never overflows the pane */
        min-height: 0;
      }

      /* hug the text — the JS autosize sets the exact height, so the only
         floor is a single line for an empty note. border-box so setting
         height = scrollHeight doesn't re-add the padding. Snug under the
         card title, aligned to the 12px inset, with breathing room under
         the last line of text. */
      :host([autogrow]) .notepad {
        box-sizing: border-box;
        overflow-y: hidden;
        min-height: 2em;
        height: 2em;
        padding: 0.25em 10px 1em 10px;
      }

      /* embedded in a card that supplies the chrome — drop our own so the
         note surface bleeds to the card's edges */
      :host([autogrow]) .wrapper {
        border: none;
        border-radius: 0;
        box-shadow: none;
      }

      .toolbar {
        background: rgba(0, 0, 0, 0.03);
        padding: 0.25em 0.5em;
        display: flex;
        min-height: 2em;
        align-items: center;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
      }

      .toolbar temba-button {
        margin-right: 0.5em;
      }

      .updated {
        font-size: 0.9em;
        flex-grow: 1;
        margin-left: 0.5em;
      }
    `;
  }

  private resizer: ResizeObserver;
  private lastWidth = 0;

  // the contact our current note was taken off - an edit only belongs to the
  // contact it was typed against, so a switch to another one re-derives
  private noteContact: string = null;

  public connectedCallback(): void {
    super.connectedCallback();
    // text rewraps when our width changes (browser resize, layout mode
    // switches), changing the height the note needs — only react to width
    // so our own height writes don't loop the observer
    this.resizer = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        const width = this.offsetWidth;
        if (width > 0 && width !== this.lastWidth) {
          this.lastWidth = width;
          this.autosize();
        }
      });
    });
    this.resizer.observe(this);
  }

  public disconnectedCallback(): void {
    this.resizer?.disconnect();
    super.disconnectedCallback();
  }

  private handleChange() {
    this.markDirty();
    // surface the unsaved state so a wrapping card can show its dirty mark
    this.fireCustomEvent(CustomEventType.DetailsChanged, { dirty: true });
    this.autosize();
  }

  private autosize() {
    if (!this.autogrow) {
      return;
    }
    const notepad = this.shadowRoot.querySelector(
      '.notepad'
    ) as HTMLTextAreaElement;
    if (notepad) {
      notepad.style.height = 'auto';
      notepad.style.height = notepad.scrollHeight + 'px';
    }
  }

  private submitChanges() {
    const notepad = this.shadowRoot.querySelector(
      '.notepad'
    ) as HTMLInputElement;
    const note = notepad.value;
    // our own write is the one delivery the dirty guard below holds out for,
    // so take the note from it once it lands
    this.postChanges({ note }).then(() => {
      this.syncNote();
    });
  }

  // takes the newest note off the contact, copied so editing it never writes
  // into the contact data we share with everything else
  private syncNote() {
    this.noteContact = this.data?.uuid || null;
    this.note =
      this.data?.notes?.length > 0
        ? { ...this.data.notes[this.data.notes.length - 1] }
        : null;
    this.fireCustomEvent(CustomEventType.DetailsChanged, {
      count: this.note && this.note.text.length > 0 ? 1 : 0,
      dirty: false
    });
    this.markClean();

    // lit dirty checks the .value binding against the last string it wrote,
    // not what's actually in the textarea, so re-deriving an unchanged note
    // wouldn't take the user's typing back off - write the note through
    const notepad = this.shadowRoot?.querySelector(
      '.notepad'
    ) as HTMLTextAreaElement;
    if (notepad) {
      notepad.value = this.note ? this.note.text : '';
    }
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    // the central watcher re-delivers the contact on any activity, not just
    // note changes, so a delivery mid-edit would otherwise drop what the user
    // has typed - hold the note until the edit is saved or abandoned. Only
    // for the contact it was typed against though: on a switch the edit goes
    // with the contact we left, so the new one's note lands right away
    if (
      changes.has('data') &&
      (!this.dirty || (this.data?.uuid || null) !== this.noteContact)
    ) {
      this.syncNote();
    }

    if (changes.has('note') || changes.has('data')) {
      this.autosize();
    }
  }

  public render(): TemplateResult {
    if (this.data) {
      return html`
        <div class="wrapper">
          <!-- prettier-ignore -->
          <textarea class="notepad" @input=${this.handleChange} .value=${this
            .note
            ? this.note.text
            : ''}></textarea>
          <div class="toolbar">
            <div class="updated">
              ${this.note
                ? html`Last updated by ${getDisplayName(this.note.created_by)}
                    <temba-date
                      value="${this.note.created_on}"
                      display="duration"
                    ></temba-date>`
                : null}
            </div>
            ${this.dirty
              ? html`
                  <temba-button
                    name="Save"
                    small
                    @click=${this.submitChanges}
                  ></temba-button>
                `
              : null}
          </div>
        </div>
      `;
    }
    return super.render();
  }
}
