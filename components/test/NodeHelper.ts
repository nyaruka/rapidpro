import { fixture, expect } from '@open-wc/testing';
import { html } from 'lit';
import { Node } from '../src/store/flow-definition';
import { assertScreenshot, getClip } from './utils.test';
import { Editor } from '../src/flow/Editor';
import '../temba-modules';

/**
 * Generic node test framework
 * Tests the complete node lifecycle: render → edit → save → validate
 *
 * This is the node configuration equivalent of ActionHelper.ts for action configurations.
 * It provides uniform testing for all types of nodes: simple wait nodes, router-based
 * split nodes, and complex form-configured nodes.
 */
export class NodeTest<T extends Node> {
  constructor(
    private nodeConfig: any,
    private nodeName: string
  ) {}

  /**
   * Renders a node in the flow editor and returns the flow node
   */
  private async renderNode(node: T, nodeUI: any): Promise<HTMLElement> {
    const mockDefinition = {
      nodes: [node],
      _ui: {
        nodes: {
          [node.uuid]: {
            type: nodeUI.type,
            position: { left: 50, top: 50 },
            ...nodeUI
          }
        }
      }
    };

    const editor = (await fixture(html`
      <temba-flow-editor>
        <div id="canvas"></div>
      </temba-flow-editor>
    `)) as Editor;

    (editor as any).definition = mockDefinition;
    (editor as any).canvasSize = { width: 400, height: 300 };
    await editor.updateComplete;

    const flowNode = editor.querySelector('temba-flow-node') as HTMLElement;
    expect(flowNode).to.exist;

    return flowNode;
  }

  /**
   * Opens the node editor for a node and returns the editor element
   */
  private async openNodeEditor(node: T, nodeUI: any): Promise<HTMLElement> {
    const nodeEditor = (await fixture(html`
      <temba-node-editor
        .node=${node}
        .nodeUI=${nodeUI}
        .isOpen=${true}
      ></temba-node-editor>
    `)) as HTMLElement;

    await (nodeEditor as any).updateComplete;

    // Wait for form data initialization if needed
    await new Promise((resolve) => setTimeout(resolve, 200));
    await (nodeEditor as any).updateComplete;

    expect(nodeEditor).to.exist;

    return nodeEditor;
  }

  /**
   * Takes a screenshot of the dialog container within a node editor
   */
  private async assertDialogScreenshot(
    el: HTMLElement,
    screenshotName: string
  ) {
    const dialog = el.shadowRoot
      ?.querySelector('temba-dialog')
      ?.shadowRoot?.querySelector('.dialog-container') as HTMLElement;
    await assertScreenshot(screenshotName, getClip(dialog));
  }

  /**
   * Complete test for a node configuration
   * 1. Renders the node in a flow node (with screenshot)
   * 2. Opens the node editor (with screenshot)
   * 3. Simulates save and validates round-trip conversion
   */
  async testNode(node: T, nodeUI: any, testName: string) {
    // Step 1: Render node in flow node
    const flowNode = await this.renderNode(node, nodeUI);

    // For execute_actions nodes, check for .body, for router nodes check for .router or .categories
    const hasContent =
      flowNode.querySelector('.body') ||
      flowNode.querySelector('.router') ||
      flowNode.querySelector('.categories') ||
      flowNode.querySelector('.action') ||
      flowNode.textContent?.trim();

    expect(hasContent).to.exist;
    await assertScreenshot(
      `nodes/${this.nodeName}/render/${testName}`,
      getClip(flowNode)
    );

    // Step 2: Open node editor
    const nodeEditor = await this.openNodeEditor(node, nodeUI);
    await this.assertDialogScreenshot(
      nodeEditor,
      `nodes/${this.nodeName}/editor/${testName}`
    );

    // Step 3: Test round-trip conversion (simulates save workflow)
    if (this.nodeConfig.toFormData && this.nodeConfig.fromFormData) {
      const formData = this.nodeConfig.toFormData(node);
      const convertedNode = this.nodeConfig.fromFormData(formData, node) as T;

      // Validate the round trip worked
      expect(convertedNode.uuid).to.equal(node.uuid);

      // Validate the converted node has expected structure
      expect(convertedNode).to.have.property('actions');
      expect(convertedNode).to.have.property('exits');

      expect(convertedNode).to.deep.equal(node);
    }
  }

  /**
   * Run basic property tests
   */
  testBasicProperties() {
    it('has correct basic properties', () => {
      expect(this.nodeConfig.type).to.be.a('string');

      // Name is optional - only some node configs have it
      if (this.nodeConfig.name) {
        expect(this.nodeConfig.name).to.be.a('string');
      }

      // EditorType is optional but recommended
      if (this.nodeConfig.editorType) {
        expect(this.nodeConfig.editorType).to.be.an('object');
        expect(this.nodeConfig.editorType.color).to.be.a('string');
        expect(this.nodeConfig.editorType.title).to.be.a('string');
        expect(this.nodeConfig.editorType.description).to.be.a('string');
      }

      // toFormData and fromFormData are optional - only needed for complex data transformations
      if (this.nodeConfig.toFormData) {
        expect(this.nodeConfig.toFormData).to.be.a('function');
      }
      if (this.nodeConfig.fromFormData) {
        expect(this.nodeConfig.fromFormData).to.be.a('function');
      }

      // Form configuration is optional
      if (this.nodeConfig.form) {
        expect(this.nodeConfig.form).to.be.an('object');
      }

      // Layout is optional
      if (this.nodeConfig.layout) {
        expect(this.nodeConfig.layout).to.be.an('array');
      }

      // Router config is optional
      if (this.nodeConfig.router) {
        expect(this.nodeConfig.router).to.be.an('object');
        expect(this.nodeConfig.router.type).to.exist;
      }

      // Render function is optional
      if (this.nodeConfig.render) {
        expect(this.nodeConfig.render).to.be.a('function');
      }
    });
  }
}
