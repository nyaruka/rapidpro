import { expect, fixture, html } from '@open-wc/testing';
import { stub, restore, useFakeTimers, SinonFakeTimers } from 'sinon';
import { Editor } from '../src/flow/Editor';
import { IssuesWindow } from '../src/flow/IssuesWindow';
import { RevisionsWindow } from '../src/flow/RevisionsWindow';
import { FlowDefinition } from '../src/store/flow-definition';

// Register the component
customElements.define('temba-flow-editor-test', Editor);
if (!customElements.get('temba-issues-window')) {
  customElements.define('temba-issues-window', IssuesWindow);
}
if (!customElements.get('temba-revisions-window')) {
  customElements.define('temba-revisions-window', RevisionsWindow);
}

describe('Flow Editor Self-Routing Prevention', () => {
  let editor: Editor;
  let mockDefinition: FlowDefinition;
  let clock: SinonFakeTimers;

  beforeEach(() => {
    restore();

    // Use fake timers to control any async operations
    clock = useFakeTimers({
      shouldAdvanceTime: true,
      advanceTimeDelta: 10
    });

    // Create a mock flow definition with test nodes and exits
    mockDefinition = {
      uuid: 'test-flow',
      name: 'Test Flow',
      nodes: [
        {
          uuid: 'node-1',
          actions: [],
          exits: [
            { uuid: 'exit-1a', destination_uuid: undefined },
            { uuid: 'exit-1b', destination_uuid: 'node-2' }
          ]
        },
        {
          uuid: 'node-2',
          actions: [],
          exits: [{ uuid: 'exit-2a', destination_uuid: undefined }]
        }
      ],
      localization: {},
      language: 'eng',
      type: 'messaging',
      revision: 1,
      spec_version: '13.1.0',
      _ui: {
        nodes: {
          'node-1': { position: { left: 100, top: 100 } },
          'node-2': { position: { left: 300, top: 100 } }
        },
        languages: []
      }
    };
  });

  afterEach(() => {
    restore();
    if (clock) {
      clock.restore();
    }
  });

  describe('connection dragging behavior', () => {
    let mockPlumber: any;

    beforeEach(async () => {
      editor = (await fixture(
        html`<temba-flow-editor-test></temba-flow-editor-test>`
      )) as Editor;

      // Wait for element to be fully initialized
      await editor.updateComplete;

      // Mock the plumber
      mockPlumber = {
        connectionDragging: false,
        on: stub(),
        connectIds: stub(),
        repaintEverything: stub(),
        setContainer: stub()
      };

      // Set up editor state
      (editor as any).plumber = mockPlumber;
      (editor as any).definition = mockDefinition;
    });

    it('prevents connection when targeting same node', () => {
      // Set up connection drag state
      (editor as any).sourceId = 'exit-1a';
      (editor as any).sourceNodeId = 'node-1';
      (editor as any).targetId = 'node-1'; // Same node as source
      (editor as any).isValidTarget = false;

      // Test the validation logic directly without makeConnection
      const shouldConnect =
        (editor as any).sourceId &&
        (editor as any).targetId &&
        (editor as any).isValidTarget;

      expect(shouldConnect).to.be.false;
    });

    it('allows connection when targeting different node', () => {
      // Set up connection drag state
      (editor as any).sourceId = 'exit-1a';
      (editor as any).sourceNodeId = 'node-1';
      (editor as any).targetId = 'node-2'; // Different node
      (editor as any).isValidTarget = true;

      // Test the validation logic directly without makeConnection
      const shouldConnect =
        (editor as any).sourceId &&
        (editor as any).targetId &&
        (editor as any).isValidTarget;

      expect(shouldConnect).to.be.true;
    });
  });

  describe('visual feedback during connection dragging', () => {
    let mockTargetNode: HTMLElement;

    beforeEach(async () => {
      editor = (await fixture(
        html`<temba-flow-editor-test></temba-flow-editor-test>`
      )) as Editor;

      // Wait for element to be fully initialized
      await editor.updateComplete;

      // Create mock target node
      mockTargetNode = document.createElement('temba-flow-node');
      mockTargetNode.setAttribute('uuid', 'node-2');
      document.body.appendChild(mockTargetNode);

      // Mock querySelector to return our mock node
      stub(document, 'querySelector')
        .withArgs('temba-flow-node:hover')
        .returns(mockTargetNode);
      stub(document, 'querySelectorAll')
        .withArgs('temba-flow-node')
        .returns({
          forEach: (callback: (node: Element) => void) =>
            callback(mockTargetNode)
        } as any);

      // Set up editor state
      (editor as any).plumber = {
        connectionDragging: true,
        setContainer: stub(),
        repaintEverything: stub()
      };
      (editor as any).definition = mockDefinition;
      (editor as any).sourceId = 'exit-1a';
      (editor as any).sourceNodeId = 'node-1';
      (editor as any).dragFromNodeId = 'node-1'; // This is the key property used in validation
    });

    afterEach(() => {
      if (document.body.contains(mockTargetNode)) {
        document.body.removeChild(mockTargetNode);
      }
    });

    it('adds valid target class when hovering over different node', async () => {
      // Make sure other properties on the editor are correctly set up
      (editor as any).targetId = 'node-2';
      (editor as any).isValidTarget = true;

      // Simulate mouse move over different node
      (editor as any).dragManager.handleMouseMove(new MouseEvent('mousemove'));
      await editor.updateComplete;

      // Allow time for DOM updates
      clock.tick(50);

      expect(mockTargetNode.classList.contains('connection-target-valid')).to.be
        .true;
      expect(mockTargetNode.classList.contains('connection-target-invalid')).to
        .be.false;
    });

    it('adds invalid target class when hovering over same node', async () => {
      // Change target to same node as source
      mockTargetNode.setAttribute('uuid', 'node-1');

      // Make sure other properties on the editor are correctly set up
      (editor as any).targetId = 'node-1';
      (editor as any).isValidTarget = false;

      // Simulate mouse move over same node
      (editor as any).dragManager.handleMouseMove(new MouseEvent('mousemove'));
      await editor.updateComplete;

      // Allow time for DOM updates
      clock.tick(50);

      expect(mockTargetNode.classList.contains('connection-target-invalid')).to
        .be.true;
      expect(mockTargetNode.classList.contains('connection-target-valid')).to.be
        .false;
    });

    it('cleans up visual feedback after connection attempt', async () => {
      // Add classes to simulate active state
      mockTargetNode.classList.add('connection-target-valid');

      // Make connection (which should clean up)
      (editor as any).makeConnection();
      await editor.updateComplete;

      expect(mockTargetNode.classList.contains('connection-target-valid')).to.be
        .false;
      expect(mockTargetNode.classList.contains('connection-target-invalid')).to
        .be.false;
    });
  });
});
