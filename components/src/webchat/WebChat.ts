/* eslint-disable @typescript-eslint/no-this-alias */
import {
  LitElement,
  PropertyValues,
  TemplateResult,
  html,
  css,
  PropertyValueMap
} from 'lit';
import { property } from 'lit/decorators.js';
import { generateUUIDv7, getCookie, setCookie } from '../utils';
import { DEFAULT_AVATAR } from './assets';
import { Chat, MsgEvent } from '../display/Chat';

interface User {
  avatar?: string;
  email: string;
  name: string;
  id: string;
}

interface MsgIn {
  id: string;
  text: string;
  time: string;
}

interface MsgOut extends MsgIn {
  user: User;
  origin: string;
}

interface SockMsg {
  type:
    | 'start_chat'
    | 'get_history'
    | 'send_msg'
    | 'ack_chat'

    // responses
    | 'chat_started'
    | 'chat_resumed'
    | 'msg_in'
    | 'msg_out'
    | 'history'

    // receiving
    | 'chat_out';
}

interface GetHistoryCmd extends SockMsg {
  before?: string;
}

interface StartChatCmd extends SockMsg {
  chat_id?: string;
}

interface SendMsgCmd extends SockMsg {
  text: string;
}

interface Ack extends SockMsg {
  msg_id: string;
}

interface MsgOutResponse extends SockMsg {
  msg_out: MsgOut;
}

interface MsgInResponse extends SockMsg {
  msg_in: MsgIn;
}

interface HistoryResponse extends SockMsg {
  history: (MsgInResponse | MsgOutResponse)[];
}

interface StartChatResponse extends SockMsg {
  chat_id: string;
}

interface ResumeChatResponse extends StartChatResponse {
  email?: string;
}

enum ChatStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected'
}

const sockToChat = function (msg: any): MsgEvent {
  const type = msg.msg_in ? 'msg_created' : 'msg_received';
  const msgContent = msg.msg_in || msg.msg_out;

  return {
    uuid: msgContent.id,
    type,
    created_on: new Date(msgContent.time),
    _user: msgContent.user,
    msg: {
      text: msgContent.text,
      channel: undefined,
      quick_replies: [],
      urn: '',
      direction: '',
      type: '',
      attachments: msgContent.attachments
    }
  };
};

export class WebChat extends LitElement {
  static get styles() {
    return css`
      :host {
        display: flex;
        align-items: center;
        align-self: center;
        --curvature: 0.6em;
        --color-primary: hsla(208, 70%, 55%, 1);
        font-family: 'Roboto', 'Helvetica Neue', sans-serif;
        font-weight: 400;
        --toggle-speed: 80ms;
        position: fixed;
        right: 0;
        bottom: 0;
        z-index: 10000;
      }

      .header {
        background: var(--color-primary);
        height: 3em;
        display: flex;
        align-items: center;
        width: 100%;
        color: rgba(255, 255, 255, 0.8);
        font-size: 0.8em;
      }

      .header slot {
        flex-grow: 1;
        padding: 1em;
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.2em;
        display: block;
      }

      .header .close-button {
        margin: 0.5em;
        color: rgba(255, 255, 255, 0.5);
        cursor: pointer;
      }

      .header .close-button:hover {
        cursor: pointer;
        color: rgba(255, 255, 255, 1);
      }

      .block {
        margin-bottom: 1em;
      }

      .time {
        text-align: center;
        font-size: 0.8em;
        color: #999;
        margin-top: 2em;
        border-top: 1px solid #f8f8f8;
        padding: 1em;
        margin-left: 4em;
        margin-right: 4em;
      }

      .first .time {
        margin-top: 0;
        border-top: none;
        padding-top: 0;
      }

      .row {
        display: flex;
        flex-direction: row;
        align-items: flex-start;
      }

      .input-panel {
        padding: 1em;
        background: #fff;
      }

      .border {
        border-top: 1px solid #e9e9e9;
        margin: 0 1em;
      }

      .avatar {
        margin-top: 0.6em;
        margin-right: 0.6em;
        flex-shrink: 0;
        width: 2em;
        height: 2em;
        overflow: hidden;
        border-radius: 100%;
        box-shadow:
          rgba(0, 0, 0, 0.1) 0px 3px 7px 0px,
          rgba(0, 0, 0, 0.2) 0px 1px 2px 0px,
          inset 0 0 0 0.15em rgba(0, 0, 0, 0.1);
      }

      .toggle {
        flex-shrink: 0;
        width: 4em;
        height: 4em;
        overflow: hidden;
        border-radius: 100%;
        box-shadow:
          rgba(0, 0, 0, 0.1) 0px 0px 1em 0.7em,
          rgba(0, 0, 0, 0.2) 0px 1px 2px 0px,
          inset 0 0 0 0.25em rgba(0, 0, 0, 0.1);
        cursor: pointer;
        transition: box-shadow var(--toggle-speed) ease-out;
        position: absolute;
        bottom: 1em;
        right: 1em;
      }

      .toggle:hover {
        box-shadow:
          rgba(0, 0, 0, 0.1) 0px 0px 1em 0.7em,
          rgba(0, 0, 0, 0.4) 0px 1px 2px 0px,
          inset 0 0 0 0.25em rgba(0, 0, 0, 0.2);
      }

      .incoming .row {
        flex-direction: row-reverse;
        margin-left: 1em;
      }

      .bubble {
        padding: 1em;
        padding-bottom: 0.5em;
        background: #fafafa;
        border-radius: var(--curvature);
        max-width: 70%;
      }

      .bubble .name {
        font-size: 0.95em;
        font-weight: 400;
        color: #888;
        margin-bottom: 0.25em;
      }

      .outgoing .bubble {
        border-top-left-radius: 0;
      }

      .incoming .bubble {
        background: var(--color-primary);
        color: white;
        border-top-right-radius: 0;
        text-align: right;
      }

      .message {
        margin-bottom: 0.5em;
        line-height: 1.2em;
      }

      .chat {
        height: 40rem;
        width: 28rem;
        border-radius: var(--curvature);
        overflow: hidden;
        box-shadow:
          rgba(0, 0, 0, 0.1) 0px 3px 7px 0px,
          rgba(0, 0, 0, 0.2) 0px 1px 2px 0px,
          rgba(0, 0, 0, 0.1) 5em 5em 5em 5em;
        position: absolute;
        bottom: 3em;
        right: 1em;
        transition: all var(--toggle-speed) ease-out;
        transform: scale(0.9);
        pointer-events: none;
        opacity: 0;
        display: flex;
        flex-direction: column;
        background: #fff;
      }

      .chat.open {
        bottom: 6em;
        opacity: 1;
        transform: scale(1);
        pointer-events: initial;
      }

      .input {
        border: none;
        flex-grow: 1;
        color: #333;
        font-size: 1em;
      }

      .input:focus {
        outline: none;
      }

      input::placeholder {
        opacity: 0.3;
      }

      .input.inactive {
        // pointer-events: none;
        // opacity: 0.3;
      }

      .active {
      }

      .send-icon {
        color: #eee;
        pointer-events: none;
        transform: rotate(-45deg);
        transition: transform 0.2s ease-out;
      }

      .pending .send-icon {
        color: var(--color-primary);
        pointer-events: initial;
        transform: rotate(0deg);
      }

      .notice {
        padding: 1em;
        background: #f8f8f8;
        color: #666;
        text-align: center;
        cursor: pointer;
      }

      .connecting .notice {
        display: flex;
        justify-content: center;
      }

      .connecting .notice temba-icon {
        margin-left: 0.5em;
      }

      .reconnect {
        color: var(--color-primary);
        text-decoration: underline;
        font-size: 0.9em;
      }

      .input:disabled {
        background: transparent !important;
      }

      temba-loading {
        justify-content: center;
        margin: 0.5em auto;
        margin-bottom: 2em;
      }

      temba-loading.hidden {
        display: none;
      }
    `;
  }

  @property({ type: String })
  channel: string;

  @property({ type: String })
  urn: string;

  @property({ type: Array })
  messageGroups: string[][] = [];

  // is our socket connection established
  @property({ type: String })
  status: ChatStatus = ChatStatus.DISCONNECTED;

  // is the chat widget open
  @property({ type: Boolean })
  open = false;

  @property({ type: Boolean })
  hasPendingText = false;

  @property({ type: String })
  host: string;

  @property({ type: String })
  activeUserAvatar: string;

  @property({ type: Boolean, attribute: false })
  blockHistoryFetching = false;

  private chat: Chat;
  private sock: WebSocket;
  private newMessageCount = 0;
  private fetchRequested: Date;
  private beforeTime: string;

  public constructor() {
    super();
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    // pre-sync status to CONNECTING to avoid setting it during updated()
    if (changed.has('open') && this.open && changed.get('open') !== undefined) {
      if (this.status === ChatStatus.DISCONNECTED) {
        this.status = ChatStatus.CONNECTING;
      }
    }
  }

  public firstUpdated(
    changed: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changed);
    this.chat = this.shadowRoot.querySelector('temba-chat');

    // Only create lightbox if one doesn't already exist
    if (!document.querySelector('temba-lightbox')) {
      const lightbox = document.createElement('temba-lightbox');
      document.querySelector('body').appendChild(lightbox);
    }
  }

  private handleReconnect() {
    this.openSocket();
  }

  private sendSockMessage(
    cmd: GetHistoryCmd | StartChatCmd | SendMsgCmd | Ack
  ) {
    // eslint-disable-next-line no-console
    console.log('out', cmd);
    this.sock.send(JSON.stringify(cmd));
  }

  private openSocket(): void {
    if (
      this.status !== ChatStatus.DISCONNECTED &&
      this.status !== ChatStatus.CONNECTING
    ) {
      return;
    }

    // avoid creating duplicate sockets
    if (this.sock && this.sock.readyState <= WebSocket.OPEN) {
      return;
    }

    this.status = ChatStatus.CONNECTING;
    const webChat = this;
    let url = `wss://localhost.textit.com/wc/connect/${this.channel}/`;
    if (this.urn) {
      url = `${url}?chat_id=${this.urn}`;
    }
    const sock = new WebSocket(url);
    this.sock = sock;
    this.sock.onclose = function () {
      webChat.status = ChatStatus.DISCONNECTED;
    };

    this.sock.onopen = function () {
      webChat.beforeTime = new Date().toISOString();
      webChat.status = ChatStatus.CONNECTED;
      webChat.urn = getCookie('temba-chat-urn');
      const cmd: StartChatCmd = { type: 'start_chat' };
      if (webChat.urn) {
        cmd.chat_id = webChat.urn;
      }
      webChat.sendSockMessage(cmd);
    };

    this.sock.onmessage = function (event: MessageEvent) {
      webChat.status = ChatStatus.CONNECTED;
      const msg = JSON.parse(event.data) as SockMsg;
      // eslint-disable-next-line no-console
      console.log('in', msg);
      if (msg.type === 'chat_started') {
        const response = msg as StartChatResponse;
        if (webChat.urn !== response.chat_id) {
          webChat.messageGroups = [];
        }
        webChat.urn = response.chat_id;
        setCookie('temba-chat-urn', response.chat_id);
        webChat.requestUpdate('messageGroups');
      } else if (msg.type === 'chat_resumed') {
        const response = msg as ResumeChatResponse;
        webChat.urn = response.chat_id;
        webChat.fetchPreviousMessages();
      } else if (msg.type === 'chat_out') {
        const response = msg as MsgOutResponse;
        webChat.chat.addMessages([sockToChat(response)], null, true);

        // ack receipt
        const ack: Ack = { type: 'ack_chat', msg_id: response.msg_out.id };
        webChat.sendSockMessage(ack);
      } else if (msg.type === 'history') {
        webChat.handleHistoryResponse(msg as HistoryResponse);
      }
    };

    this.sock.onerror = function () {
      webChat.status = ChatStatus.DISCONNECTED;
    };
  }

  public fetchPreviousMessages() {
    if (!this.blockHistoryFetching) {
      this.fetchRequested = new Date();
      this.blockHistoryFetching = true;
      this.chat.fetching = true;

      const cmd: GetHistoryCmd = {
        type: 'get_history',
        before: this.beforeTime
      };
      this.fetchRequested = new Date();
      this.sendSockMessage(cmd);
    }
  }

  private handleHistoryResponse(response: HistoryResponse) {
    const messages = response.history.reverse();
    if (messages.length > 0) {
      const oldestMessage = messages[0];
      if (oldestMessage['msg_in']) {
        const msgIn = (oldestMessage as MsgInResponse).msg_in;
        this.beforeTime = msgIn.time;
      } else if (oldestMessage['msg_out']) {
        const msgOut = (oldestMessage as MsgOutResponse).msg_out;
        this.beforeTime = msgOut.time;
      }
    }

    // convert messages to chat messages
    this.chat.addMessages(messages.map(sockToChat), this.fetchRequested);
  }

  public fetchComplete() {
    this.blockHistoryFetching = false;
  }

  private focusInput() {
    const input = this.shadowRoot.querySelector('.input') as any;
    if (input) {
      input.focus();
    }
  }

  public updated(
    changed: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changed);

    if (this.open && changed.has('open') && changed.get('open') !== undefined) {
      if (this.status === ChatStatus.CONNECTING) {
        this.openSocket();
      }
    }

    if (changed.has('status')) {
      if (this.status === ChatStatus.CONNECTED) {
        this.focusInput();
      }
    }
  }

  public openChat(): void {
    this.open = true;
  }

  public handleKeyUp(event: any) {
    if (this.hasPendingText && event.key === 'Enter') {
      this.sendPendingMessage();
    }

    this.hasPendingText = event.target.value.length > 0;
  }

  private sendPendingMessage() {
    if (this.status === ChatStatus.CONNECTED) {
      const input = this.shadowRoot.querySelector('.input') as any;
      const text = input.value;
      input.value = '';

      const msg: SendMsgCmd = {
        // msg_id: `pending-${this.newMessageCount++}`,
        type: 'send_msg',
        text: text
        // time: new Date().toISOString()
      };

      this.sendSockMessage(msg);

      const date = new Date();

      this.chat.addMessages(
        [
          {
            uuid: generateUUIDv7(),
            type: 'msg_received',
            msg: { text },
            created_on: date
          } as MsgEvent
        ],
        date,
        true
      );
      this.hasPendingText = input.value.length > 0;
    }
  }

  private handleClickInputPanel(event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    const input = this.shadowRoot.querySelector('.input') as any;
    input.focus();
  }

  private toggleChat() {
    this.open = !this.open;
  }

  public render(): TemplateResult {
    return html`
      <div class="chat ${this.status} ${this.open ? 'open' : ''}">
        <div class="header">
          <slot name="header">${this.urn ? this.urn : 'Chat'}</slot>
          <temba-icon
            name="close"
            size="1.3"
            class="close-button"
            @click=${this.toggleChat}
          ></temba-icon>
        </div>

        <temba-chat
          @temba-scroll-threshold=${this.fetchPreviousMessages}
          @temba-fetch-complete=${this.fetchComplete}
        ></temba-chat>

        ${this.status === ChatStatus.DISCONNECTED
          ? html`<div class="notice">
              <div>This chat is not currently connected.</div>
              <div class="reconnect" @click=${this.handleReconnect}>
                Click here to reconnect
                <div></div>
              </div>
            </div>`
          : null}
        ${this.status === ChatStatus.CONNECTING
          ? html`<div class="notice">
              <div>Connecting</div>
              <temba-icon name="progress_spinner" spin></temba-icon>
            </div>`
          : null}
        ${this.status === ChatStatus.CONNECTED
          ? html` <div class="border"></div>
              <div
                class="row input-panel ${this.hasPendingText ? 'pending' : ''}"
                @click=${this.handleClickInputPanel}
              >
                <input
                  class="input ${this.status === ChatStatus.CONNECTED
                    ? 'active'
                    : 'inactive'}"
                  type="text"
                  placeholder="Message.."
                  ?disabled=${this.status !== ChatStatus.CONNECTED}
                  @keydown=${this.handleKeyUp}
                />
                <temba-icon
                  tabindex="1"
                  class="send-icon"
                  name="send"
                  size="1"
                  clickable
                  @click=${this.sendPendingMessage}
                ></temba-icon>
              </div>`
          : null}
      </div>

      <div @click=${this.toggleChat}>
        <div
          class="toggle"
          style="background: center / contain no-repeat url(${this
            .activeUserAvatar || DEFAULT_AVATAR})"
        ></div>
      </div>
    `;
  }
}
