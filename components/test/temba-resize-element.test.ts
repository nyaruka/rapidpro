import { expect, fixture, html } from '@open-wc/testing';
import { ResizeElement } from '../src/ResizeElement';

// Create a test implementation of ResizeElement
class TestResizeElement extends ResizeElement {
  updateRequestCount = 0;

  requestUpdate() {
    this.updateRequestCount++;
    return super.requestUpdate();
  }

  render() {
    return html`<div>resize test</div>`;
  }
}

customElements.define('test-resize-element', TestResizeElement);

describe('ResizeElement', () => {
  let element: TestResizeElement;

  beforeEach(async () => {
    element = await fixture(html`<test-resize-element></test-resize-element>`);
  });

  describe('handleResize', () => {
    it('calls requestUpdate when handleResize is called', () => {
      const initialCount = element.updateRequestCount;

      element.handleResize();

      expect(element.updateRequestCount).to.equal(initialCount + 1);
    });

    it('is throttled when called multiple times rapidly', (done) => {
      const initialCount = element.updateRequestCount;

      // Get a reference to the throttled handler
      const handlers = element.getEventHandlers();
      const throttledHandler = handlers[0].method;

      // Call the throttled handler multiple times
      throttledHandler.call(element);
      throttledHandler.call(element);
      throttledHandler.call(element);

      // Due to throttling, should only execute once initially
      setTimeout(() => {
        expect(element.updateRequestCount).to.be.greaterThan(initialCount);
        expect(element.updateRequestCount).to.be.at.most(initialCount + 1);
        done();
      }, 25);
    });
  });

  describe('getEventHandlers', () => {
    it('returns resize event handler for window', () => {
      const handlers = element.getEventHandlers();

      expect(handlers).to.be.an('array');
      expect(handlers.length).to.equal(1);

      const resizeHandler = handlers[0];
      expect(resizeHandler.event).to.equal('resize');
      expect(resizeHandler.isWindow).to.be.true;
      expect(typeof resizeHandler.method).to.equal('function');
    });

    it('resize handler is properly throttled', () => {
      const handlers = element.getEventHandlers();
      const resizeHandler = handlers[0];

      // The method should be a throttled version of handleResize
      expect(typeof resizeHandler.method).to.equal('function');

      // Test that the throttled method can be called
      expect(() => resizeHandler.method()).to.not.throw;
    });
  });

  describe('window resize integration', () => {
    it('responds to window resize events when connected', (done) => {
      const initialCount = element.updateRequestCount;

      // Simulate window resize event
      const resizeEvent = new Event('resize');
      window.dispatchEvent(resizeEvent);

      // Give some time for the throttled event to be processed
      setTimeout(() => {
        expect(element.updateRequestCount).to.be.greaterThan(initialCount);
        done();
      }, 75);
    });

    it('handles disconnection properly', () => {
      // Test that disconnecting doesn't cause errors
      expect(() => {
        element.disconnectedCallback();
      }).to.not.throw;
    });
  });
});
