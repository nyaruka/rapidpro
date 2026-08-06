import { expect, fixture, html } from '@open-wc/testing';
import { CanvasNode } from '../src/flow/CanvasNode';
import {
  FlowDefinition,
  Node,
  NodeUI,
  SendMsg
} from '../src/store/flow-definition';
import { zustand } from '../src/store/AppState';
import '../temba-modules';

describe('Shift+drag copy actions', () => {
  let node1: Node;
  let node1UI: NodeUI;
  let node2: Node;
  let node2UI: NodeUI;
  let storeElement: HTMLElement;

  const setupStore = (
    nodes: Node[],
    uis: Record<string, NodeUI>,
    localization: Record<string, Record<string, any>> = {}
  ) => {
    const flowDefinition: FlowDefinition = {
      uuid: 'test-flow',
      name: 'Test Flow',
      language: 'eng',
      type: 'messaging' as const,
      revision: 1,
      spec_version: '14.3',
      localization,
      nodes,
      _ui: {
        nodes: uis,
        languages: []
      }
    };
    zustand.getState().setFlowContents({
      definition: flowDefinition,
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: nodes.length, languages: 1 },
        locals: []
      }
    });
  };

  before(() => {
    storeElement = document.createElement('temba-store');
    document.body.appendChild(storeElement);
  });

  after(() => {
    storeElement?.remove();
  });

  beforeEach(() => {
    node1 = {
      uuid: 'node-1',
      actions: [
        {
          type: 'send_msg',
          uuid: 'action-1',
          text: 'First message',
          quick_replies: ['Yes']
        } as SendMsg,
        {
          type: 'send_msg',
          uuid: 'action-2',
          text: 'Second message',
          quick_replies: []
        } as SendMsg
      ],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };

    node1UI = {
      position: { left: 100, top: 100 },
      type: 'execute_actions',
      config: {}
    };

    node2 = {
      uuid: 'node-2',
      actions: [
        {
          type: 'send_msg',
          uuid: 'action-3',
          text: 'Third message',
          quick_replies: []
        } as SendMsg
      ],
      exits: [{ uuid: 'exit-2', destination_uuid: null }]
    };

    node2UI = {
      position: { left: 400, top: 100 },
      type: 'execute_actions',
      config: {}
    };
  });

  describe('node-to-node drop with isCopy', () => {
    it('should copy action with new UUID when isCopy is true', async () => {
      setupStore([node1, node2], { 'node-1': node1UI, 'node-2': node2UI });

      const node2Element = await fixture<CanvasNode>(html`
        <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
      `);
      await node2Element.updateComplete;

      // Set up drag info so the drop handler has a drop index
      const dragOverEvent = new CustomEvent('action-drag-over', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseY: 150
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dragOverEvent);
      await node2Element.updateComplete;

      // Drop with isCopy=true
      const dropEvent = new CustomEvent('action-drop', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseX: 400,
          mouseY: 150,
          isCopy: true
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dropEvent);
      await node2Element.updateComplete;

      // Verify the action was added to node2 with a new UUID
      const state = zustand.getState();
      const updatedNode2 = state.flowDefinition.nodes.find(
        (n: Node) => n.uuid === 'node-2'
      );
      expect(updatedNode2.actions.length).to.equal(2);
      // New action appended at end (drop index defaults to actions.length)
      const addedAction = updatedNode2.actions[1];
      expect(addedAction.uuid).to.not.equal('action-1'); // New UUID
      expect((addedAction as SendMsg).text).to.equal('First message');

      // Verify source node is unchanged (action not removed)
      const updatedNode1 = state.flowDefinition.nodes.find(
        (n: Node) => n.uuid === 'node-1'
      );
      expect(updatedNode1.actions.length).to.equal(2);
      expect(updatedNode1.actions[0].uuid).to.equal('action-1');
    });

    it('should move action when isCopy is false', async () => {
      setupStore([node1, node2], { 'node-1': node1UI, 'node-2': node2UI });

      const node2Element = await fixture<CanvasNode>(html`
        <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
      `);
      await node2Element.updateComplete;

      // Set up drag info
      const dragOverEvent = new CustomEvent('action-drag-over', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseY: 150
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dragOverEvent);
      await node2Element.updateComplete;

      // Drop with isCopy=false (move)
      const dropEvent = new CustomEvent('action-drop', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseX: 400,
          mouseY: 150,
          isCopy: false
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dropEvent);
      await node2Element.updateComplete;

      // Verify action was added to node2 with original UUID
      const state = zustand.getState();
      const updatedNode2 = state.flowDefinition.nodes.find(
        (n: Node) => n.uuid === 'node-2'
      );
      expect(updatedNode2.actions.length).to.equal(2);
      expect(updatedNode2.actions[1].uuid).to.equal('action-1');

      // Verify action was removed from source node
      const updatedNode1 = state.flowDefinition.nodes.find(
        (n: Node) => n.uuid === 'node-1'
      );
      expect(updatedNode1.actions.length).to.equal(1);
      expect(updatedNode1.actions[0].uuid).to.equal('action-2');
    });

    it('should copy localizations when isCopy is true', async () => {
      setupStore(
        [node1, node2],
        { 'node-1': node1UI, 'node-2': node2UI },
        {
          spa: {
            'action-1': { text: ['Primer mensaje'], quick_replies: ['Sí'] }
          },
          fra: {
            'action-1': { text: ['Premier message'] }
          }
        }
      );

      const node2Element = await fixture<CanvasNode>(html`
        <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
      `);
      await node2Element.updateComplete;

      // Set up drag info
      const dragOverEvent = new CustomEvent('action-drag-over', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseY: 150
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dragOverEvent);
      await node2Element.updateComplete;

      // Drop with isCopy=true
      const dropEvent = new CustomEvent('action-drop', {
        detail: {
          action: node1.actions[0],
          sourceNodeUuid: 'node-1',
          actionIndex: 0,
          mouseX: 400,
          mouseY: 150,
          isCopy: true
        },
        bubbles: false
      });
      node2Element.dispatchEvent(dropEvent);
      await node2Element.updateComplete;

      // Find the new action UUID
      const state = zustand.getState();
      const updatedNode2 = state.flowDefinition.nodes.find(
        (n: Node) => n.uuid === 'node-2'
      );
      const newActionUuid = updatedNode2.actions[1].uuid;
      expect(newActionUuid).to.not.equal('action-1');

      // Verify localizations were copied to new UUID
      const localization = state.flowDefinition.localization;
      expect(localization.spa[newActionUuid]).to.deep.equal({
        text: ['Primer mensaje'],
        quick_replies: ['Sí']
      });
      expect(localization.fra[newActionUuid]).to.deep.equal({
        text: ['Premier message']
      });

      // Verify original localizations still exist
      expect(localization.spa['action-1']).to.deep.equal({
        text: ['Primer mensaje'],
        quick_replies: ['Sí']
      });
    });
  });
});
