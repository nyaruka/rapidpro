import { property } from 'lit/decorators.js';
import { TemplateResult, html, css, PropertyValues } from 'lit';
import { Button } from '../display/Button';
import { CustomEventType } from '../interfaces';
import { styleMap } from 'lit-html/directives/style-map.js';
import { getClasses } from '../utils';
import { ResizeElement } from '../ResizeElement';

export enum ButtonType {
  PRIMARY = 'primary',
  SECONDARY = 'secondary',
  DESTRUCTIVE = 'destructive'
}
export class DialogButton {
  name?: string;
  id?: string;
  details?: any;
  type?: string;
  closes?: boolean;
}

export class Dialog extends ResizeElement {
  public static readonly UNSAVED_CHANGES_MESSAGE =
    'You have unsaved changes. Are you sure you want to discard them?';

  static get widths(): { [size: string]: string } {
    return {
      small: '400px',
      medium: '600px',
      large: '655px',
      xlarge: '800px'
    };
  }

  static get styles() {
    return css`
      :host {
        position: absolute;
        z-index: 10000;
        font-family: var(--font-family);
        background: white;
      }

      .flex-grow {
        flex-grow: 1;
      }

      .flex {
        display: flex;
        flex-direction: column;
        width: 100%;
        position: relative;
        left: 0px;
        top: 0px;
        align-items: center;
        height: 100vh;
      }

      .mobile .flex {
        height: 100%;
        position: fixed;
      }

      .mobile .grow-top {
        flex-grow: 0;
      }

      .mobile .grow-bottom {
        flex-grow: 0;
      }

      .grow-top {
        flex-grow: 1;
      }

      .grow-bottom {
        flex-grow: 3;
      }

      .bottom-padding {
        padding: 3rem;
      }

      .dialog-mask {
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        opacity: 0;
        position: fixed;
        top: 0px;
        left: 0px;
        transition: opacity linear calc(var(--transition-speed) / 2ms);
        pointer-events: none;
      }

      .mobile.dialog-mask .dialog-container {
        border-radius: 0px;
      }

      .dialog-mask .dialog-container {
        position: relative;
        transition:
          transform var(--transition-speed) ease-in-out,
          opacity ease-in-out calc(var(--transition-speed) - 50ms);
        border-radius: var(--curvature);
        box-shadow: 0px 0px 2px 4px rgba(0, 0, 0, 0.06);
        overflow: hidden;
        transform: scale(0.9) translatey(2em);
        background: white;
        margin: auto;
        display: flex;
        flex-direction: column;
      }

      .dialog-body {
        background: #fff;
        overflow-y: auto;
        overflow-x: hidden;
        flex-grow: 1;
      }

      .dialog-mask.dialog-open {
        opacity: 1;
        pointer-events: auto;
      }

      .dialog-mask.dialog-open .dialog-container {
        top: inherit;
      }

      .dialog-mask.dialog-animation-end .dialog-container {
        transform: scale(1) translate(0, 0) !important;
      }

      .dialog-mask.dialog-ready .dialog-container {
        transform: none;
      }

      .dialog-mask.dialog-loading .dialog-container {
        margin-top: -10000px;
      }

      .header-text {
        display: flex;
        flex-direction: row;
        align-items: center;
        font-size: 20px;
        padding: 12px 20px var(--dialog-header-padding-bottom, 12px);
        color: var(--header-text);
        background: var(--header-bg);
      }

      /* "flat" variant: header/footer share the body's white background
         and lose their inner padding so the dialog reads as one
         continuous surface. Use for content-focused dialogs that don't
         need the tinted chrome. */
      :host([variant='flat']) .header-text {
        background: #fff;
        color: var(--color-text);
        padding-bottom: 0;
      }

      :host([variant='flat']) .dialog-footer {
        background: #fff;
        padding-top: 0;
      }

      .header-text .title {
        flex-grow: 1;
      }

      .header-text .status {
        font-size: 0.6em;
        font-weight: bold;
      }

      .dialog-footer {
        background: var(--dialog-footer-background, var(--color-primary-light));
        padding: var(--dialog-footer-padding-top, 10px) 10px 10px;
        display: flex;
        flex-flow: row;
        align-items: center;
      }

      temba-button {
        margin-left: 10px;
      }

      .dialog-body temba-loading {
        position: absolute;
        right: 12px;
        margin-top: -30px;
        padding-bottom: 9px;
        display: none;
      }

      #page-loader {
        text-align: center;
        display: block;
        position: relative;
        opacity: 0;
        margin: auto;
        margin-top: 30px;
        width: 154px;
        transition: opacity calc(var(--transition-speed) * 5ms) ease-in
          calc(var(--transition-speed * 2));
        visibility: hidden;
      }

      .dialog-mask.dialog-loading #page-loader {
        opacity: 1;
        visibility: visible;
      }

      #submit-loader {
        flex-grow: 1;
        text-align: right;
      }
    `;
  }

  @property({ type: Boolean })
  open: boolean;

  @property()
  header: string;

  @property()
  body: string;

  @property({ type: Boolean })
  submitting: boolean;

  @property({ type: Boolean })
  destructive: boolean;

  @property({ type: Boolean })
  disabled: boolean;

  @property({ type: Boolean })
  loading: boolean;

  @property({ type: Boolean })
  hideOnClick: boolean;

  @property({ type: String, reflect: true })
  variant: string;

  @property({ type: Boolean })
  noFocus: boolean;

  @property()
  size = 'medium';

  @property({ type: String })
  primaryButtonName = 'Ok';

  @property({ type: String })
  cancelButtonName = 'Cancel';

  @property({ type: String })
  width = null;

  @property()
  submittingName = 'Saving';

  @property()
  animationEnd: boolean;

  @property()
  ready: boolean;

  @property({ type: Array })
  buttons: DialogButton[] = [];

  @property({ attribute: false })
  onButtonClicked: (button: Button) => void;

  // when set, consulted instead of the built-in edit tracking to decide
  // whether escape should confirm before dismissing — for owners that can
  // compare actual values (and so ignore edits that were reverted)
  @property({ attribute: false })
  checkForChanges?: () => boolean;

  @property({ type: Number })
  originX: number | null = null;

  @property({ type: Number })
  originY: number | null = null;

  // whether any input/change has bubbled from our content since opening;
  // the default signal that escape would discard the user's edits
  private contentEdited = false;

  // elements the user has actually interacted with (pointer or key) since the
  // dialog opened; components fire synthetic change events on programmatic
  // value changes (initialization of preset values, async option resolution),
  // so an input/change only counts as an edit when it originates from an
  // element the user has touched
  private interactedElements = new WeakSet<EventTarget>();

  scrollOffset: any = 0;

  public constructor() {
    super();
  }

  private updateButtons() {
    this.buttons = [];
    if (this.cancelButtonName) {
      this.buttons.push({
        name: this.cancelButtonName,
        type: ButtonType.SECONDARY,
        closes: true
      });
    }

    if (this.primaryButtonName) {
      this.buttons.push({
        name: this.primaryButtonName,
        type: ButtonType.PRIMARY
      });
    }
  }

  public willUpdate(changes: PropertyValues) {
    super.willUpdate(changes);

    if (changes.has('cancelButtonName') || changes.has('primaryButtonName')) {
      this.updateButtons();
    }

    if (changes.has('open') && this.open) {
      if (this.originX == null && this.originY == null) {
        // Default animation (no origin): set animationEnd before render
        this.animationEnd = true;
      }
    }
  }

  public updated(changes: Map<string, any>) {
    super.updated(changes);

    if (changes.has('open')) {
      this.contentEdited = false;
      this.interactedElements = new WeakSet<EventTarget>();
      const body = document.querySelector('body');

      if (this.open) {
        if (this.originX != null && this.originY != null) {
          // Spring-from-origin animation: measure final position, then
          // set initial transform at click point and transition to center
          const ox = this.originX;
          const oy = this.originY;
          this.originX = null;
          this.originY = null;

          requestAnimationFrame(() => {
            const container = this.shadowRoot?.querySelector(
              '.dialog-container'
            ) as HTMLElement;
            if (container) {
              const rect = container.getBoundingClientRect();
              const cx = rect.left + rect.width / 2;
              const cy = rect.top + rect.height / 2;
              const dx = ox - cx;
              const dy = oy - cy;

              // Disable transition so we can set the start position instantly
              container.style.transition = 'none';
              container.style.transform = `translate(${dx}px, ${dy}px) scale(0.2)`;
              // Force reflow to register the start position
              container.getBoundingClientRect();

              // Re-enable transition and trigger animation to final position
              container.style.transition = '';
              this.animationEnd = true;
              window.setTimeout(() => {
                this.ready = true;
                this.animationEnd = false;
                container.style.transform = '';
              }, 400);
            }
          });
        } else {
          // Default animation (no origin): animationEnd already set in willUpdate
          window.setTimeout(() => {
            this.ready = true;
            this.animationEnd = false;
          }, 400);
        }

        this.scrollOffset = -document.documentElement.scrollTop;
        body.style.position = 'fixed';
        body.style.overflowY = 'scroll';
        body.style.top = this.scrollOffset + 'px';
        body.style.width = '100%';
        body.style.overflowY = 'hidden';
      } else {
        body.style.position = '';
        body.style.overflowY = '';
        body.style.width = '';
        body.style.marginRight = '';
        body.style.paddingRight = '0px';
        window.scrollTo(0, parseInt(this.scrollOffset || '0') * -1);
      }

      // make sure our buttons aren't in progress on show
      if (this.open && !changes.get('open')) {
        this.shadowRoot
          .querySelectorAll('temba-button')
          .forEach((button: Button) => {
            if (button) button.submitting = false;
          });
      } else {
        window.setTimeout(() => {
          this.ready = false;
        }, 400);
      }
    }
  }

  public focusFirstInput(): void {
    window.setTimeout(() => {
      let input = this.querySelector(
        'temba-textinput, temba-completion, input[type="text"], textarea'
      ) as any;
      if (input) {
        input = input.textInputElement || input.inputElement || input;
        if (!input.readOnly) {
          input.focus();
          input.click();
        }
      }
    }, 100);
  }

  public handleClick(evt: MouseEvent) {
    const button = evt.currentTarget as Button;
    if (!button.disabled) {
      let detail: DialogButton = {};
      if (button.index >= 0 && button.index < this.buttons.length) {
        detail = this.buttons[button.index];
      }

      this.fireCustomEvent(CustomEventType.ButtonClicked, { button, detail });
      if (button.name === this.cancelButtonName || (detail && detail.closes)) {
        this.open = false;
      }
    }
  }

  private getDocumentHeight(): number {
    const body = document.body;
    const html = document.documentElement;
    return Math.max(
      body.scrollHeight,
      body.offsetHeight,
      html.clientHeight,
      html.scrollHeight,
      html.offsetHeight
    );
  }

  private clickCancel() {
    const cancel = this.getCancelButton();
    if (cancel) {
      cancel.click();
    }
  }

  public getCancelButton(): Button {
    return this.shadowRoot.querySelector(
      `temba-button[name='${this.cancelButtonName}']`
    );
  }

  public getPrimaryButton(): Button {
    return this.shadowRoot.querySelector(`temba-button[primary]`);
  }

  public hasUnsavedChanges(): boolean {
    return this.checkForChanges ? this.checkForChanges() : this.contentEdited;
  }

  private handleContentInteraction(event: Event) {
    // the path covers the interacted element and its ancestors, so a change
    // fired later by a containing component (e.g. a select whose inner input
    // was clicked) still matches
    event.composedPath().forEach((el) => this.interactedElements.add(el));
  }

  private handleContentEdited(event: Event) {
    // only the originating element is checked (not its ancestors, which the
    // paths of unrelated interactions also pass through)
    if (this.interactedElements.has(event.composedPath()[0])) {
      this.contentEdited = true;
    }
  }

  private handleKeyUp(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (
        this.hasUnsavedChanges() &&
        !window.confirm(Dialog.UNSAVED_CHANGES_MESSAGE)
      ) {
        return;
      }
      this.clickCancel();
    }
  }

  private handleClickMask(event: MouseEvent) {
    if (this.hideOnClick) {
      const id = (event.target as HTMLElement).id;
      if (id === 'dialog-mask' || id === 'dialog-bg') {
        this.fireCustomEvent(CustomEventType.DialogHidden);
        this.clickCancel();
      }
    }
  }

  public show(): void {
    this.open = true;
  }

  public hide(): void {
    this.open = false;
  }

  public render(): TemplateResult {
    const dialogStyle = {
      width: this.width
    };

    if (!this.width) {
      dialogStyle['width'] = Dialog.widths[this.size];
    }

    if (this.isMobile()) {
      dialogStyle['width'] = '100%';
      dialogStyle['height'] = '100%';
      delete dialogStyle['maxWidth'];
    }

    const header = this.header
      ? html`
          <div class="dialog-header">
            <div class="header-text">
              <div class="title">${this.header}</div>
            </div>
          </div>
        `
      : null;

    return html`
      <div
        id="dialog-mask"
        @click=${this.handleClickMask}
        class="dialog-mask ${getClasses({
          'dialog-open': this.open,
          'dialog-loading': this.loading,
          'dialog-animation-end': this.animationEnd,
          'dialog-ready': this.ready,
          mobile: this.isMobile()
        })}"
      >
        <div style="position: absolute; width: 100%;">
          <temba-loading
            id="page-loader"
            units="6"
            size="12"
            color="#ccc"
          ></temba-loading>
        </div>

        <div class="flex">
          <div
            class="grow-top"
            style="${this.isMobile() ? 'flex-grow:0' : ''}"
          ></div>
          <div
            @keyup=${this.handleKeyUp}
            @keydown=${this.handleContentInteraction}
            @pointerdown=${this.handleContentInteraction}
            @input=${this.handleContentEdited}
            @change=${this.handleContentEdited}
            style=${styleMap(dialogStyle)}
            class="dialog-container"
          >
            ${header}
            <div class="dialog-body" @keypress=${this.handleKeyUp}>
              ${this.body ? this.body : html`<slot></slot>`}
              <temba-loading units="6" size="8"></temba-loading>
            </div>

            ${
              // the gutter check is render-time only (not reactive) - fine
              // while consumers slot gutter content declaratively up front
              this.buttons.length > 0 || this.querySelector('[slot="gutter"]')
                ? html`<div class="dialog-footer">
                    <div class="flex-grow">
                      <slot name="gutter"></slot>
                    </div>
                    ${this.buttons.map(
                      (button: DialogButton, index) => html`
                        <temba-button
                          name=${button.name}
                          ?destructive=${button.type == 'primary' &&
                          this.destructive}
                          ?primary=${button.type == 'primary' &&
                          !this.destructive}
                          ?secondary=${button.type == 'secondary'}
                          ?submitting=${this.submitting &&
                          button.type == 'primary'}
                          ?disabled=${this.disabled && !button.closes}
                          index=${index}
                          @click=${this.handleClick}
                        ></temba-button>
                      `
                    )}
                  </div>`
                : null
            }
          </div>
          <div class="grow-bottom"></div>
        </div>
      </div>
    `;
  }
}
