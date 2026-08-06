import { useFakeTimers, stub, SinonStub } from 'sinon';
import { WebChat } from '../src/webchat/WebChat';
import {
  assertScreenshot,
  getClip,
  getComponent,
  mockNow,
  mouseClickElement
} from '../test/utils.test';
import { expect, assert } from '@open-wc/testing';

let clock: any;

const TAG = 'temba-webchat';

const getWebChat = async (attrs: any = {}) => {
  const webChat = (await getComponent(TAG, attrs, '', 400, 600)) as WebChat;

  // Ensure component is fully initialized before returning
  await webChat.updateComplete;
  clock.tick(100);
  await webChat.updateComplete;

  return webChat;
};

// Mock WebSocket
class MockWebSocket {
  public onopen: ((event: Event) => void) | null = null;
  public onclose: ((event: CloseEvent) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public readyState: number = 0;
  public url: string;
  public sentMessages: string[] = [];
  public autoOpen: boolean = true;

  constructor(url: string) {
    this.url = url;
    // Only auto-open if enabled
    if (this.autoOpen) {
      // Use synchronous execution instead of setTimeout to avoid clock advancing issues
      this.readyState = 1; // OPEN
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  // Test helper to manually open connection
  manualOpen() {
    this.readyState = 1; // OPEN
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  // Test helper to simulate incoming messages
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(
        new MessageEvent('message', { data: JSON.stringify(data) })
      );
    }
  }

  // Test helper to simulate errors
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('temba-webchat', () => {
  let originalWebSocket: any;
  let mockWebSocket: MockWebSocket;
  let webSocketStub: SinonStub;
  let cookieStub: SinonStub;
  let mockedNow: SinonStub;

  beforeEach(() => {
    mockedNow = mockNow('2021-03-31T00:31:00.000-00:00');

    // Mock WebSocket
    originalWebSocket = window.WebSocket;
    webSocketStub = stub(window, 'WebSocket').callsFake((url: string) => {
      mockWebSocket = new MockWebSocket(url);
      mockWebSocket.autoOpen = false; // Disable auto-open by default
      return mockWebSocket as any;
    });

    // Mock document.cookie
    cookieStub = stub(document, 'cookie').value('');

    // Use fake timers but with a shorter timeout to avoid test hanging
    clock = useFakeTimers({
      shouldAdvanceTime: true,
      advanceTimeDelta: 10
    });
  });

  afterEach(() => {
    clock.restore();
    webSocketStub.restore();
    cookieStub.restore();
    mockedNow.restore();
    window.WebSocket = originalWebSocket;
  });

  describe('Component Initialization', () => {
    it('creates component with default properties', async () => {
      const webChat = await getWebChat();

      assert.instanceOf(webChat, WebChat);
      expect(webChat.open).to.equal(false);
      expect(webChat.status).to.equal('disconnected');
      expect(webChat.hasPendingText).to.equal(false);
      expect(webChat.messageGroups).to.deep.equal([]);
      expect(webChat.blockHistoryFetching).to.equal(false);
    });

    it('accepts channel and urn properties', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        urn: 'test-urn-123'
      });

      expect(webChat.channel).to.equal('test-channel');
      expect(webChat.urn).to.equal('test-urn-123');
    });

    it('accepts host and activeUserAvatar properties', async () => {
      const webChat = await getWebChat({
        host: 'example.com',
        activeUserAvatar: 'https://example.com/avatar.jpg'
      });

      expect(webChat.host).to.equal('example.com');
      expect(webChat.activeUserAvatar).to.equal(
        'https://example.com/avatar.jpg'
      );
    });

    it('initializes chat component on first update', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      // Check that the chat component was initialized
      const chatElement = webChat.shadowRoot.querySelector('temba-chat');
      expect(chatElement).to.exist;
    });
  });

  describe('UI Rendering', () => {
    it('renders closed chat widget by default', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      await assertScreenshot('webchat/closed-widget', getClip(webChat));
    });

    it('renders opened chat widget', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true
      });

      await assertScreenshot('webchat/opened-widget', getClip(webChat));
    });

    it('renders connecting state', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      expect(webChat.open).to.equal(false);
      expect(webChat.status).to.equal('disconnected');

      // Click to open the widget, which should trigger connecting state
      const toggleElement = webChat.shadowRoot.querySelector('.toggle');
      expect(toggleElement).to.exist;

      await mouseClickElement(toggleElement);
      await webChat.updateComplete;
      clock.tick(50);

      // Now it should be open and connecting
      expect(webChat.open).to.equal(true);
      expect(webChat.status).to.equal('connecting');

      // await assertScreenshot('webchat/connecting-state', getClip(webChat));
    });

    it('renders disconnected state with reconnect option', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'disconnected'
      });

      await assertScreenshot('webchat/disconnected-state', getClip(webChat));
    });

    it('renders connected state with input field', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'connected'
      });

      // the cursor is blinking, we need to account for it in our screenshot by making it transparent
      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      expect(inputField).to.exist;
      inputField.style.caretColor = 'transparent';

      await assertScreenshot('webchat/connected-state', getClip(webChat));
    });
  });

  describe('Chat Toggle Functionality', () => {
    it('toggles chat open/closed', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      expect(webChat.open).to.equal(false);

      // Click the toggle element
      const toggleElement = webChat.shadowRoot.querySelector('.toggle');
      expect(toggleElement).to.exist;

      await mouseClickElement(toggleElement);
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.open).to.equal(true);

      // Click toggle again
      await mouseClickElement(toggleElement);
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.open).to.equal(false);
    });

    it('toggles chat via close button', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true
      });

      expect(webChat.open).to.equal(true);

      // Click close button in header
      const closeButton = webChat.shadowRoot.querySelector('.close-button');
      expect(closeButton).to.exist;

      (closeButton as HTMLElement).click();
      await webChat.updateComplete;

      expect(webChat.open).to.equal(false);
    });

    it('opens chat programmatically', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      expect(webChat.open).to.equal(false);

      webChat.openChat();
      await webChat.updateComplete;

      expect(webChat.open).to.equal(true);
    });
  });

  describe('Socket Connection Management', () => {
    it('opens socket when chat is opened', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      expect(webChat.status).to.equal('disconnected');

      // Open chat - this should trigger socket connection
      webChat.open = true;
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.status).to.equal('connecting');
      expect(webSocketStub.called).to.be.true;
      expect(mockWebSocket.url).to.include('test-channel');

      // Now simulate the socket opening
      mockWebSocket.manualOpen();
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.status).to.equal('connected');
    });

    it('does not open socket if already connecting or connected', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      // First connection
      webChat.open = true;
      await webChat.updateComplete;
      await clock.tick(0);

      const firstCallCount = webSocketStub.callCount;

      // Try to connect again while connecting
      webChat.open = false;
      webChat.open = true;
      await webChat.updateComplete;
      await clock.tick(0);

      // Should not create another socket
      expect(webSocketStub.callCount).to.equal(firstCallCount);
    });

    it('constructs correct WebSocket URL with channel', async () => {
      const webChat = await getWebChat({
        channel: 'my-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      clock.tick(50);

      expect(mockWebSocket.url).to.equal(
        'wss://localhost.textit.com/wc/connect/my-channel/'
      );
    });

    it('includes urn in WebSocket URL when present', async () => {
      const webChat = await getWebChat({
        channel: 'my-channel',
        urn: 'chat-123'
      });

      webChat.open = true;
      await webChat.updateComplete;
      clock.tick(50);

      expect(mockWebSocket.url).to.equal(
        'wss://localhost.textit.com/wc/connect/my-channel/?chat_id=chat-123'
      );
    });

    it('sends start_chat command on socket open', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;

      // Manually open the socket to trigger the start_chat command
      mockWebSocket.manualOpen();
      await webChat.updateComplete;
      clock.tick(100);

      expect(mockWebSocket.sentMessages.length).to.be.at.least(1);
      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).to.equal('start_chat');
    });

    it('includes chat_id in start_chat command when urn is present', async () => {
      // Set the cookie directly in document.cookie
      cookieStub.value('temba-chat-urn=existing-chat-123');

      const webChat = await getWebChat({
        channel: 'test-channel',
        urn: 'existing-chat-123'
      });

      webChat.open = true;
      await webChat.updateComplete;

      mockWebSocket.manualOpen();
      await webChat.updateComplete;
      clock.tick(50);

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).to.equal('start_chat');
      // The chat_id should be 'existing-chat-123' either from the urn property or cookie
      expect(sentMessage.chat_id).to.equal('existing-chat-123');
    });

    it('handles socket close event', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.status).to.equal('connecting');

      mockWebSocket.close();
      await webChat.updateComplete;
      clock.tick(50);

      expect(webChat.status).to.equal('disconnected');
    });

    it('handles socket error event', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;

      expect(webChat.status).to.equal('connecting');

      mockWebSocket.simulateError();
      await webChat.updateComplete;

      expect(webChat.status).to.equal('disconnected');
    });

    it('reconnects when reconnect button is clicked', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'disconnected'
      });

      const reconnectButton = webChat.shadowRoot.querySelector('.reconnect');
      expect(reconnectButton).to.exist;

      await mouseClickElement(reconnectButton);
      await webChat.updateComplete;

      expect(webSocketStub.called).to.be.true;
      expect(webChat.status).to.equal('connecting');
    });
  });

  describe('Message Handling', () => {
    it('handles chat_started message', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      expect(webChat.status).to.equal('connected');

      // Simulate chat_started message
      mockWebSocket.simulateMessage({
        type: 'chat_started',
        chat_id: 'new-chat-456'
      });
      await webChat.updateComplete;

      expect(webChat.urn).to.equal('new-chat-456');
      expect(webChat.messageGroups).to.deep.equal([]);
    });

    it('handles chat_resumed message and fetches history', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate chat_resumed message
      mockWebSocket.simulateMessage({
        type: 'chat_resumed',
        chat_id: 'resumed-chat-789'
      });
      await webChat.updateComplete;

      expect(webChat.urn).to.equal('resumed-chat-789');

      // Should have sent get_history command
      expect(mockWebSocket.sentMessages.length).to.be.greaterThan(1);
      const lastMessage = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(lastMessage.type).to.equal('get_history');
    });

    it('handles chat_out message and sends ack', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Simulate incoming message
      mockWebSocket.simulateMessage({
        type: 'chat_out',
        msg_out: {
          id: 'msg-123',
          text: 'Hello from server',
          time: '2021-03-31T00:31:00.000Z',
          user: {
            id: 'user-1',
            name: 'Test User',
            email: 'test@example.com'
          }
        }
      });
      await webChat.updateComplete;

      // Should have sent ack
      expect(mockWebSocket.sentMessages.length).to.equal(
        initialMessageCount + 1
      );
      const ackMessage = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(ackMessage.type).to.equal('ack_chat');
      expect(ackMessage.msg_id).to.equal('msg-123');
    });

    it('handles history response', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate history response
      mockWebSocket.simulateMessage({
        type: 'history',
        history: [
          {
            msg_out: {
              id: 'msg-1',
              text: 'First message',
              time: '2021-03-31T00:30:00.000Z',
              user: { id: 'user-1', name: 'User', email: 'user@example.com' }
            }
          },
          {
            msg_in: {
              id: 'msg-2',
              text: 'Second message',
              time: '2021-03-31T00:30:30.000Z'
            }
          }
        ]
      });
      await webChat.updateComplete;

      // Should have updated beforeTime and unblocked history fetching
      expect(webChat.blockHistoryFetching).to.equal(false);
    });

    it('clears messages when chat_id changes', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        urn: 'old-chat-123'
      });

      webChat.messageGroups = [['existing', 'messages']];

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate chat_started with different chat_id
      mockWebSocket.simulateMessage({
        type: 'chat_started',
        chat_id: 'new-chat-456'
      });
      await webChat.updateComplete;

      expect(webChat.urn).to.equal('new-chat-456');
      expect(webChat.messageGroups).to.deep.equal([]);
    });

    it('keeps messages when chat_id is the same', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // First, simulate a chat_started to set the URN
      mockWebSocket.simulateMessage({
        type: 'chat_started',
        chat_id: 'same-chat-123'
      });
      await webChat.updateComplete;

      // Now set some messages
      webChat.messageGroups = [['existing', 'messages']];
      await webChat.updateComplete;

      // Simulate another chat_started with the same chat_id
      mockWebSocket.simulateMessage({
        type: 'chat_started',
        chat_id: 'same-chat-123'
      });
      await webChat.updateComplete;

      expect(webChat.urn).to.equal('same-chat-123');
      expect(webChat.messageGroups).to.deep.equal([['existing', 'messages']]);
    });
  });

  describe('User Input and Message Sending', () => {
    it('updates hasPendingText on keyup', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'connected'
      });

      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      expect(inputField).to.exist;

      expect(webChat.hasPendingText).to.equal(false);

      // Simulate typing
      inputField.value = 'Hello';
      inputField.dispatchEvent(new KeyboardEvent('keydown', { key: 'h' }));
      await webChat.updateComplete;

      expect(webChat.hasPendingText).to.equal(true);

      // Clear input
      inputField.value = '';
      inputField.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Backspace' })
      );
      await webChat.updateComplete;

      expect(webChat.hasPendingText).to.equal(false);
    });

    it('sends message on Enter key', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Ensure the socket is properly set
      expect(webChat.status).to.equal('connected');

      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      inputField.value = 'Test message';
      webChat.hasPendingText = true;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Call handleKeyUp directly with Enter key event
      webChat.handleKeyUp({ key: 'Enter', target: inputField });
      await webChat.updateComplete;

      // Should have sent message
      expect(mockWebSocket.sentMessages.length).to.equal(
        initialMessageCount + 1
      );
      const sentMessage = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(sentMessage.type).to.equal('send_msg');
      expect(sentMessage.text).to.equal('Test message');

      // input should be cleared and hasPendingText should be false
      expect(inputField.value).to.equal('');
      expect(webChat.hasPendingText).to.equal(false);
    });

    it('sends message via send button click', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;

      inputField.value = 'Button click message';
      webChat.hasPendingText = true;
      await webChat.updateComplete;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // call sendPendingMessage directly since it's a private method called by click handler
      (webChat as any).sendPendingMessage();
      await webChat.updateComplete;

      // should have sent message
      expect(mockWebSocket.sentMessages.length).to.equal(
        initialMessageCount + 1
      );
      const sentMessage = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(sentMessage.type).to.equal('send_msg');
      expect(sentMessage.text).to.equal('Button click message');
    });

    it('focuses input when input panel is clicked', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'connected'
      });

      const inputPanel = webChat.shadowRoot.querySelector('.input-panel');
      expect(inputPanel).to.exist;

      // Mock focus method
      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      let focusCalled = false;
      inputField.focus = () => {
        focusCalled = true;
      };

      await mouseClickElement(inputPanel);

      expect(focusCalled).to.be.true;
    });

    it('does not send message when disconnected', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true
      });

      // Keep the status as disconnected - don't connect the socket
      expect(webChat.status).to.equal('disconnected');

      // Find input field - it might not exist in disconnected state
      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      if (inputField) {
        inputField.value = 'Should not send';
        webChat.hasPendingText = true;

        // Try to send message by calling handleKeyUp
        webChat.handleKeyUp({ key: 'Enter', target: inputField });
        await webChat.updateComplete;
      }

      // Should not have created any WebSocket connections
      expect(webSocketStub.called).to.be.false;
    });
  });

  describe('History Fetching', () => {
    it('fetches previous messages when requested', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Manually call fetchPreviousMessages
      webChat.fetchPreviousMessages();
      await webChat.updateComplete;

      expect(webChat.blockHistoryFetching).to.equal(true);
      expect(mockWebSocket.sentMessages.length).to.equal(
        initialMessageCount + 1
      );

      const historyRequest = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(historyRequest.type).to.equal('get_history');
      expect(historyRequest.before).to.exist;
    });

    it('does not fetch when already fetching', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.blockHistoryFetching = true;

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Try to fetch - should be blocked
      webChat.fetchPreviousMessages();
      await webChat.updateComplete;

      expect(mockWebSocket.sentMessages.length).to.equal(initialMessageCount);
    });

    it('completes fetch and unblocks history fetching', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.blockHistoryFetching = true;

      webChat.fetchComplete();

      expect(webChat.blockHistoryFetching).to.equal(false);
    });
  });

  describe('Edge Cases and Additional Coverage', () => {
    it('handles keyup events that are not Enter', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      inputField.value = 'Some text';

      // Test with non-Enter key
      webChat.handleKeyUp({ key: 'a', target: inputField });
      await webChat.updateComplete;

      expect(webChat.hasPendingText).to.equal(true);

      // Test with empty value
      inputField.value = '';
      webChat.handleKeyUp({ key: 'Backspace', target: inputField });
      await webChat.updateComplete;

      expect(webChat.hasPendingText).to.equal(false);
    });

    it('does not send message on Enter if no pending text', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const inputField = webChat.shadowRoot.querySelector(
        '.input'
      ) as HTMLInputElement;
      inputField.value = '';
      webChat.hasPendingText = false;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Try to send with Enter but no pending text
      webChat.handleKeyUp({ key: 'Enter', target: inputField });
      await webChat.updateComplete;

      // Should not have sent any new messages
      expect(mockWebSocket.sentMessages.length).to.equal(initialMessageCount);
    });

    it('updates status when open changes from false to true', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      expect(webChat.status).to.equal('disconnected');

      // Open the chat for the first time
      webChat.open = true;
      await webChat.updateComplete;

      expect(webChat.status).to.equal('connecting');
      expect(webSocketStub.called).to.be.true;
    });

    it('focuses input when status changes to connected', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      // Open chat to trigger connection
      webChat.open = true;
      await webChat.updateComplete;

      expect(webChat.status).to.equal('connecting');

      // Mock focus method before the input is rendered
      let focusCalled = false;
      const originalFocus = HTMLInputElement.prototype.focus;
      HTMLInputElement.prototype.focus = function () {
        focusCalled = true;
      };

      // Manually open socket to trigger status change to connected
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Restore original focus
      HTMLInputElement.prototype.focus = originalFocus;

      // Focus should have been called when status changed to connected
      expect(focusCalled).to.be.true;
    });

    it('handles focus input when input element does not exist', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'disconnected'
      });

      // Try to focus input when it might not exist
      (webChat as any).focusInput();

      // Should not throw an error
      expect(true).to.be.true;
    });

    it('handles empty history response', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate empty history response
      mockWebSocket.simulateMessage({
        type: 'history',
        history: []
      });
      await webChat.updateComplete;

      expect(webChat.blockHistoryFetching).to.equal(false);
    });

    it('handles message with msg_in in history response', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate history response with msg_in first
      mockWebSocket.simulateMessage({
        type: 'history',
        history: [
          {
            msg_in: {
              id: 'msg-1',
              text: 'Incoming message',
              time: '2021-03-31T00:30:00.000Z'
            }
          }
        ]
      });
      await webChat.updateComplete;

      expect(webChat.blockHistoryFetching).to.equal(false);
    });

    it('prevents event propagation on input panel click', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel',
        open: true,
        status: 'connected'
      });

      const inputPanel = webChat.shadowRoot.querySelector('.input-panel');
      expect(inputPanel).to.exist;

      let preventDefaultCalled = false;
      let stopPropagationCalled = false;

      const mockEvent = {
        preventDefault: () => {
          preventDefaultCalled = true;
        },
        stopPropagation: () => {
          stopPropagationCalled = true;
        }
      };

      (webChat as any).handleClickInputPanel(mockEvent);

      expect(preventDefaultCalled).to.be.true;
      expect(stopPropagationCalled).to.be.true;
    });

    it('handles unknown message types gracefully', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      // Simulate unknown message type
      mockWebSocket.simulateMessage({
        type: 'unknown_message_type',
        data: 'some data'
      });
      await webChat.updateComplete;

      // Should not throw an error
      expect(true).to.be.true;
    });
  });

  describe('Integration with Chat Component', () => {
    it('listens to scroll threshold event for history fetching', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.open = true;
      await webChat.updateComplete;
      mockWebSocket.manualOpen();
      await webChat.updateComplete;

      const chatElement = webChat.shadowRoot.querySelector('temba-chat');
      expect(chatElement).to.exist;

      const initialMessageCount = mockWebSocket.sentMessages.length;

      // Simulate scroll threshold event
      chatElement.dispatchEvent(new CustomEvent('temba-scroll-threshold'));
      await webChat.updateComplete;

      // Should have triggered history fetch
      expect(mockWebSocket.sentMessages.length).to.equal(
        initialMessageCount + 1
      );
      const historyRequest = JSON.parse(
        mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]
      );
      expect(historyRequest.type).to.equal('get_history');
    });

    it('listens to fetch complete event', async () => {
      const webChat = await getWebChat({
        channel: 'test-channel'
      });

      webChat.blockHistoryFetching = true;

      const chatElement = webChat.shadowRoot.querySelector('temba-chat');
      expect(chatElement).to.exist;

      // Simulate fetch complete event
      chatElement.dispatchEvent(new CustomEvent('temba-fetch-complete'));

      expect(webChat.blockHistoryFetching).to.equal(false);
    });
  });
});
