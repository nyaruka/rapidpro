import { TemplateResult, css, html } from 'lit';
import { RapidElement } from '../RapidElement';
import { property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';

interface ToastMessage {
  id: number;
  text: string;
  level: 'info' | 'warning' | 'error';
  visible?: boolean;
  time: Date;
  removeTime?: Date;
}

export class Toast extends RapidElement {
  @property({ type: Array })
  messages: ToastMessage[] = [];

  @property({ type: Number, attribute: 'duration' })
  staleDuration = 5000;

  @property({ type: Number, attribute: 'animation' })
  animationDuration = 200;

  @property({ type: Boolean, attribute: 'error-sticky' })
  errorSticky = false;

  @property({ type: Boolean, attribute: 'warning-sticky' })
  warningSticky = false;

  @property({ type: Boolean, attribute: 'info-sticky' })
  infoSticky = false;

  static styles = css`
    :host {
      position: fixed;
      width: 400px;
      z-index: 10000;
      right: 0;
    }

    .message {
      background-color: rgba(50, 50, 50, 0.85);
      background-color: rgba(255, 255, 255, 0.97);
      color: rgba(0, 0, 0, 0.85);
      padding: 0.5em 1em;
      margin: 0.75em;
      border-radius: 0.5em;
      display: flex;
      transition-property: transform, opacity;
      transition-timing-function: ease-in-out;
      transform: translateY(-100%);
      opacity: 0;
      box-shadow: rgba(0, 0, 0, 0.2) 0px 0px 3em 2px;
      border: 2px solid rgba(0, 0, 0, 0.3);
    }

    .message.visible {
      transform: translateY(0);
      opacity: 1;
    }

    .message.info {
    }

    .message.warning {
      color: rgba(255, 167, 0, 0.9);
    }

    .message.error {
      border-color: var(--color-error);
      color: var(--color-error);
    }

    .message.removing {
      opacity: 0;
      transform: translateY(-100%);
    }

    temba-icon {
      cursor: pointer;
      padding-left: 1em;
      opacity: 0;
      transition: all 200ms ease-in-out;
    }

    .message:hover temba-icon {
      opacity: 1;
    }

    temba-icon:hover {
      transform: scale(1.3) translateX(-0.1em);
    }

    .message .text {
      flex-grow: 1;
    }

    .info {
    }
  `;

  public checkForStaleMessages() {
    const now = new Date();

    // ignore sticky messages
    const staleMessages = this.messages.filter((message) => {
      if (message.level === 'error' && this.errorSticky) {
        return false;
      }
      if (message.level === 'warning' && this.warningSticky) {
        return false;
      }
      if (message.level === 'info' && this.infoSticky) {
        return false;
      }
      return true;
    });

    staleMessages.forEach((message) => {
      // error messages do not remove themselves
      if (now.getTime() - message.time.getTime() > this.staleDuration) {
        this.removeMessage(message);
      }
    });

    if (this.messages.length === 0 && this.checker) {
      window.clearInterval(this.checker);
      this.checker = 0;
    }
  }

  private checker: number;
  private messageId: number = 0;

  public addMessages(messages: ToastMessage[]) {
    messages.forEach((message) => {
      this.addMessage(message.text, message.level);
    });
  }

  public addMessage(text: string, level: 'info' | 'warning' | 'error') {
    const message: ToastMessage = {
      id: ++this.messageId,
      text,
      level,
      time: new Date()
    };
    this.messages.push(message);

    window.setTimeout(() => {
      message.visible = true;
      this.requestUpdate('messages');
    }, 100);

    this.requestUpdate('messages');

    if (this.checker) {
      window.clearInterval(this.checker);
      this.checker = 0;
    }

    this.checker = window.setInterval(
      this.checkForStaleMessages.bind(this),
      1000
    );
  }

  public info(message: string) {
    this.addMessage(message, 'info');
  }

  public warning(message: string) {
    this.addMessage(message, 'warning');
  }

  public error(message: string) {
    this.addMessage(message, 'error');
  }

  public removeMessage(message: ToastMessage) {
    message.removeTime = new Date();
    window.setTimeout(() => {
      this.messages = this.messages.filter((m) => m !== message);
      this.requestUpdate('messages');
    }, this.animationDuration);

    this.requestUpdate('messages');
  }

  private handleMessageClicked(e: MouseEvent) {
    const ele = e.target as HTMLElement;
    const id = parseInt(ele.getAttribute('message_id'));
    const message = this.messages.find((m) => m.id === id);
    if (message) {
      this.removeMessage(message);
    }
  }

  public render(): TemplateResult {
    return html`
      ${repeat(
        this.messages,
        (message) => message.id,
        (message) => html`
          <div
            style="transition-duration: ${this.animationDuration}ms"
            class="message ${message.level} ${message.visible
              ? 'visible'
              : ''} ${message.removeTime ? 'removing' : ''}"
          >
            <div class="text">${message.text}</div>
            <temba-icon
              name="close"
              size="1.3"
              message_id="${message.id}"
              @click=${this.handleMessageClicked}
            ></temba-icon>
          </div>
        `
      )}
    `;
  }
}
