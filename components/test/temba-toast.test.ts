import { fixture, assert, expect } from '@open-wc/testing';
import { Toast } from '../src/display/Toast';

// Register the component if it's not already registered
if (!customElements.get('temba-toast')) {
  customElements.define('temba-toast', Toast);
}

export const createToast = async (attrs: any = {}) => {
  const attrString = Object.keys(attrs)
    .map((key) => `${key}="${attrs[key]}"`)
    .join(' ');

  return (await fixture(`<temba-toast ${attrString}></temba-toast>`)) as Toast;
};

describe('temba-toast', () => {
  it('can be created', async () => {
    const toast = await createToast();

    assert.instanceOf(toast, Toast);
    expect(toast.messages).to.deep.equal([]);
    expect(toast.staleDuration).to.equal(5000);
    expect(toast.animationDuration).to.equal(200);
    expect(toast.errorSticky).to.be.false;
    expect(toast.warningSticky).to.be.false;
    expect(toast.infoSticky).to.be.false;
  });

  it('can set properties via attributes', async () => {
    const toast = await createToast({
      duration: '3000',
      animation: '300',
      'error-sticky': 'true',
      'warning-sticky': 'true',
      'info-sticky': 'true'
    });

    expect(toast.staleDuration).to.equal(3000);
    expect(toast.animationDuration).to.equal(300);
    expect(toast.errorSticky).to.be.true;
    expect(toast.warningSticky).to.be.true;
    expect(toast.infoSticky).to.be.true;
  });

  it('adds info message', async () => {
    const toast = await createToast();
    toast.info('This is an info message');

    expect(toast.messages).to.have.length(1);
    expect(toast.messages[0].text).to.equal('This is an info message');
    expect(toast.messages[0].level).to.equal('info');
    expect(toast.messages[0].id).to.equal(1);
    expect(toast.messages[0].time).to.be.instanceOf(Date);
    expect(toast.messages[0].visible).to.be.undefined;
  });

  it('adds warning message', async () => {
    const toast = await createToast();
    toast.warning('This is a warning message');

    expect(toast.messages).to.have.length(1);
    expect(toast.messages[0].text).to.equal('This is a warning message');
    expect(toast.messages[0].level).to.equal('warning');
    expect(toast.messages[0].id).to.equal(1);
  });

  it('adds error message', async () => {
    const toast = await createToast();
    toast.error('This is an error message');

    expect(toast.messages).to.have.length(1);
    expect(toast.messages[0].text).to.equal('This is an error message');
    expect(toast.messages[0].level).to.equal('error');
    expect(toast.messages[0].id).to.equal(1);
  });

  it('adds multiple messages with incrementing IDs', async () => {
    const toast = await createToast();
    toast.info('First message');
    toast.warning('Second message');
    toast.error('Third message');

    expect(toast.messages).to.have.length(3);
    expect(toast.messages[0].id).to.equal(1);
    expect(toast.messages[1].id).to.equal(2);
    expect(toast.messages[2].id).to.equal(3);
  });

  it('adds multiple messages using addMessages', async () => {
    const toast = await createToast();
    const messages = [
      {
        text: 'First message',
        level: 'info' as const,
        id: 1,
        time: new Date()
      },
      {
        text: 'Second message',
        level: 'warning' as const,
        id: 2,
        time: new Date()
      },
      {
        text: 'Third message',
        level: 'error' as const,
        id: 3,
        time: new Date()
      }
    ];

    toast.addMessages(messages);

    expect(toast.messages).to.have.length(3);
    expect(toast.messages[0].text).to.equal('First message');
    expect(toast.messages[0].level).to.equal('info');
    expect(toast.messages[1].text).to.equal('Second message');
    expect(toast.messages[1].level).to.equal('warning');
    expect(toast.messages[2].text).to.equal('Third message');
    expect(toast.messages[2].level).to.equal('error');
  });

  it('makes messages visible after delay', async () => {
    const toast = await createToast();
    toast.info('Test message');

    // Initially not visible
    expect(toast.messages[0].visible).to.be.undefined;

    await waitFor(200);

    expect(toast.messages[0].visible).to.be.true;
  });

  it('removes message manually', async () => {
    const toast = await createToast();
    toast.info('Test message');

    const message = toast.messages[0];
    expect(toast.messages).to.have.length(1);

    toast.removeMessage(message);

    // Message should have removeTime set
    expect(message.removeTime).to.be.instanceOf(Date);

    // Wait for animation to complete
    await new Promise((resolve) => setTimeout(resolve, 250));

    expect(toast.messages).to.have.length(0);
  });

  it('handles message click to remove', async () => {
    const toast = await createToast();
    toast.info('Test message');

    // Wait for render
    await toast.updateComplete;

    const closeIcon = toast.shadowRoot?.querySelector(
      'temba-icon[name="close"]'
    ) as HTMLElement;
    expect(closeIcon).to.exist;

    // Simulate click
    closeIcon.click();

    // Wait for animation
    await new Promise((resolve) => setTimeout(resolve, 250));

    expect(toast.messages).to.have.length(0);
  });

  it('handles invalid message ID in click handler', async () => {
    const toast = await createToast();
    toast.info('Test message');

    await toast.updateComplete;

    // Create a mock event with invalid message_id
    const mockEvent = {
      target: {
        getAttribute: () => 'invalid'
      }
    } as any;

    // Should not throw error
    expect(() => {
      (toast as any).handleMessageClicked(mockEvent);
    }).to.not.throw();

    // Message should still exist
    expect(toast.messages).to.have.length(1);
  });

  it('handles missing message in click handler', async () => {
    const toast = await createToast();
    toast.info('Test message');

    await toast.updateComplete;

    // Create a mock event with non-existent message_id
    const mockEvent = {
      target: {
        getAttribute: () => '999'
      }
    } as any;

    // Should not throw error
    expect(() => {
      (toast as any).handleMessageClicked(mockEvent);
    }).to.not.throw();

    // Message should still exist
    expect(toast.messages).to.have.length(1);
  });

  it('checks for stale messages', async () => {
    const toast = await createToast({ duration: '100' }); // 100ms duration
    toast.info('Test message');

    // Wait for message to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Manually trigger stale check
    toast.checkForStaleMessages();

    // Wait for removal animation
    await new Promise((resolve) => setTimeout(resolve, 250));

    expect(toast.messages).to.have.length(0);
  });

  it('respects sticky info messages', async () => {
    const toast = await createToast({
      duration: '100',
      'info-sticky': 'true'
    });
    toast.info('Sticky info message');

    // Wait for message to become "stale"
    await new Promise((resolve) => setTimeout(resolve, 150));

    toast.checkForStaleMessages();

    // Message should still exist because it's sticky
    expect(toast.messages).to.have.length(1);
  });

  it('respects sticky warning messages', async () => {
    const toast = await createToast({
      duration: '100',
      'warning-sticky': 'true'
    });
    toast.warning('Sticky warning message');

    // Wait for message to become "stale"
    await new Promise((resolve) => setTimeout(resolve, 150));

    toast.checkForStaleMessages();

    // Message should still exist because it's sticky
    expect(toast.messages).to.have.length(1);
  });

  it('respects sticky error messages', async () => {
    const toast = await createToast({
      duration: '100',
      'error-sticky': 'true'
    });
    toast.error('Sticky error message');

    // Wait for message to become "stale"
    await new Promise((resolve) => setTimeout(resolve, 150));

    toast.checkForStaleMessages();

    // Message should still exist because it's sticky
    expect(toast.messages).to.have.length(1);
  });

  it('clears interval when no messages remain', async () => {
    const toast = await createToast({ duration: '100' });
    toast.info('Test message');

    // Verify interval is set
    expect((toast as any).checker).to.be.greaterThan(0);

    // Wait for stale and removal
    await new Promise((resolve) => setTimeout(resolve, 150));
    toast.checkForStaleMessages();

    // Wait for the removeMessage animation to complete
    await new Promise((resolve) => setTimeout(resolve, 250));

    // Now trigger checkForStaleMessages again to clear the interval
    toast.checkForStaleMessages();

    // Interval should be cleared
    expect((toast as any).checker).to.equal(0);
  });

  it('clears existing interval when adding new message', async () => {
    const toast = await createToast();
    toast.info('First message');

    const firstChecker = (toast as any).checker;
    expect(firstChecker).to.be.greaterThan(0);

    toast.info('Second message');

    // Should have new interval
    expect((toast as any).checker).to.be.greaterThan(0);
    expect((toast as any).checker).to.not.equal(firstChecker);
  });

  it('renders messages with correct CSS classes', async () => {
    const toast = await createToast();
    toast.info('Info message');
    toast.warning('Warning message');
    toast.error('Error message');

    await toast.updateComplete;

    const messages = toast.shadowRoot?.querySelectorAll('.message');
    expect(messages).to.have.length(3);

    expect(messages?.[0]).to.have.class('info');
    expect(messages?.[1]).to.have.class('warning');
    expect(messages?.[2]).to.have.class('error');
  });

  it('renders messages with visible class after delay', async () => {
    const toast = await createToast();
    toast.info('Test message');

    await toast.updateComplete;

    const message = toast.shadowRoot?.querySelector('.message');
    expect(message).to.not.have.class('visible');

    // Wait for visibility timeout
    await new Promise((resolve) => setTimeout(resolve, 150));
    await toast.updateComplete;

    expect(message).to.have.class('visible');
  });

  it('renders messages with removing class when removed', async () => {
    const toast = await createToast();
    toast.info('Test message');

    await toast.updateComplete;

    const messageData = toast.messages[0];
    toast.removeMessage(messageData);

    await toast.updateComplete;

    const message = toast.shadowRoot?.querySelector('.message');
    expect(message).to.have.class('removing');
  });

  it('renders close icons with correct message_id', async () => {
    const toast = await createToast();
    toast.info('Test message');

    await toast.updateComplete;

    const closeIcon = toast.shadowRoot?.querySelector(
      'temba-icon[name="close"]'
    );
    expect(closeIcon?.getAttribute('message_id')).to.equal('1');
  });

  it('renders correct animation duration styles', async () => {
    const toast = await createToast({ animation: '500' });
    toast.info('Test message');

    await toast.updateComplete;

    const message = toast.shadowRoot?.querySelector('.message') as HTMLElement;
    expect(message?.style.transitionDuration).to.equal('500ms');
  });
});
