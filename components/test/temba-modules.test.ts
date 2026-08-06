import { expect } from '@open-wc/testing';
import { addCustomElement } from '../temba-modules';

describe('temba-modules', () => {
  describe('addCustomElement', () => {
    it('defines a custom element when not already defined', () => {
      // Create a mock component class
      class TestComponent extends HTMLElement {}

      // Ensure the element is not already defined
      const elementName = 'test-custom-element-' + Date.now();
      expect(window.customElements.get(elementName)).to.be.undefined;

      // Define the element
      addCustomElement(elementName, TestComponent);

      // Verify it's now defined
      expect(window.customElements.get(elementName)).to.equal(TestComponent);
    });

    it('does not redefine a custom element when already defined', () => {
      // Create mock component classes
      class FirstComponent extends HTMLElement {}
      class SecondComponent extends HTMLElement {}

      const elementName = 'test-existing-element-' + Date.now();

      // Define the element first time
      addCustomElement(elementName, FirstComponent);
      expect(window.customElements.get(elementName)).to.equal(FirstComponent);

      // Try to define again with different component
      addCustomElement(elementName, SecondComponent);

      // Should still be the first component
      expect(window.customElements.get(elementName)).to.equal(FirstComponent);
      expect(window.customElements.get(elementName)).to.not.equal(
        SecondComponent
      );
    });

    it('handles multiple different elements', () => {
      class ComponentA extends HTMLElement {}
      class ComponentB extends HTMLElement {}

      const elementA = 'test-element-a-' + Date.now();
      const elementB = 'test-element-b-' + Date.now();

      addCustomElement(elementA, ComponentA);
      addCustomElement(elementB, ComponentB);

      expect(window.customElements.get(elementA)).to.equal(ComponentA);
      expect(window.customElements.get(elementB)).to.equal(ComponentB);
    });
  });
});
