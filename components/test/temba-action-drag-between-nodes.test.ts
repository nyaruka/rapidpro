import { expect, fixture, html } from '@open-wc/testing';
import { CanvasNode } from '../src/flow/CanvasNode';
import { Node, NodeUI, SendMsg } from '../src/store/flow-definition';
import '../temba-modules';

describe('Drag actions between nodes', () => {
  let node1: Node;
  let node1UI: NodeUI;
  let node2: Node;
  let node2UI: NodeUI;

  beforeEach(() => {
    // Create test nodes
    node1 = {
      uuid: 'node-1',
      actions: [
        {
          type: 'send_msg',
          uuid: 'action-1',
          text: 'First message',
          quick_replies: []
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

  it('should render execute_actions node with sortable list', async () => {
    const node1Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node1} .ui=${node1UI}></temba-flow-node>
    `);

    await node1Element.updateComplete;

    // Verify node renders with sortable list
    const sortableList = node1Element.querySelector('temba-sortable-list');
    expect(sortableList).to.exist;

    // Verify actions are rendered
    const actions = node1Element.querySelectorAll('.action.sortable');
    expect(actions.length).to.equal(2);
  });

  it('should show placeholder in target node during drag', async () => {
    const node2Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
    `);

    await node2Element.updateComplete;

    // Simulate action-drag-over event from Editor
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

    // Check that placeholder is rendered
    const placeholder = node2Element.querySelector('.drop-placeholder');
    expect(placeholder).to.exist;
  });

  it('should handle drag-over event and store external drag info', async () => {
    const node2Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
    `);

    await node2Element.updateComplete;

    // Simulate drag over
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

    // Verify that external drag info is stored (check internal state)
    const externalDragInfo = (node2Element as any).externalDragInfo;
    expect(externalDragInfo).to.exist;
    expect(externalDragInfo.action.uuid).to.equal('action-1');
    expect(externalDragInfo.sourceNodeUuid).to.equal('node-1');
  });

  it('should calculate correct drop index based on mouse position', async () => {
    const node2Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
    `);

    await node2Element.updateComplete;

    // Get action element bounds to calculate positions
    let actionElement = node2Element.querySelector(
      '.action.sortable:not(.drop-placeholder)'
    ) as HTMLElement;
    expect(actionElement).to.exist;

    let rect = actionElement.getBoundingClientRect();
    const topY = rect.top + 5; // Near top of first action

    // Drag over at top
    const dragOverEventTop = new CustomEvent('action-drag-over', {
      detail: {
        action: node1.actions[0],
        sourceNodeUuid: 'node-1',
        actionIndex: 0,
        mouseY: topY
      },
      bubbles: false
    });
    node2Element.dispatchEvent(dragOverEventTop);
    await node2Element.updateComplete;

    // Check drop index is at beginning
    let externalDragInfo = (node2Element as any).externalDragInfo;
    expect(externalDragInfo.dropIndex).to.equal(0);

    // Re-query bounds after placeholder has been rendered (it shifts the action)
    actionElement = node2Element.querySelector(
      '.action.sortable:not(.drop-placeholder)'
    ) as HTMLElement;
    rect = actionElement.getBoundingClientRect();
    const bottomY = rect.bottom + 5; // Below the (shifted) action

    // Drag over at bottom
    const dragOverEventBottom = new CustomEvent('action-drag-over', {
      detail: {
        action: node1.actions[0],
        sourceNodeUuid: 'node-1',
        actionIndex: 0,
        mouseY: bottomY
      },
      bubbles: false
    });
    node2Element.dispatchEvent(dragOverEventBottom);
    await node2Element.updateComplete;

    // Check drop index is at end
    externalDragInfo = (node2Element as any).externalDragInfo;
    expect(externalDragInfo.dropIndex).to.equal(1);
  });

  it('should not accept drops from the same node', async () => {
    const node1Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node1} .ui=${node1UI}></temba-flow-node>
    `);

    await node1Element.updateComplete;

    // Try to drop action from node-1 onto node-1
    const dragOverEvent = new CustomEvent('action-drag-over', {
      detail: {
        action: node1.actions[0],
        sourceNodeUuid: 'node-1', // Same as target
        actionIndex: 0,
        mouseY: 150
      },
      bubbles: false
    });
    node1Element.dispatchEvent(dragOverEvent);
    await node1Element.updateComplete;

    // Verify external drag info was NOT stored (rejected due to same source)
    const externalDragInfo = (node1Element as any).externalDragInfo;
    expect(externalDragInfo).to.be.null;
  });

  it('should clear external drag state and hide placeholder', async () => {
    const node2Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node2} .ui=${node2UI}></temba-flow-node>
    `);

    await node2Element.updateComplete;

    // Simulate drag over
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

    // Verify placeholder exists
    let placeholder = node2Element.querySelector('.drop-placeholder');
    expect(placeholder).to.exist;

    // Clear the external drag state (simulating drag leaving the node)
    (node2Element as any).externalDragInfo = null;
    // Trigger re-render
    node2Element.requestUpdate();
    await node2Element.updateComplete;

    // Verify placeholder is gone
    placeholder = node2Element.querySelector('.drop-placeholder');
    expect(placeholder).to.not.exist;
  });

  it('should have sortable list for internal drag support', async () => {
    const node1Element = await fixture<CanvasNode>(html`
      <temba-flow-node .node=${node1} .ui=${node1UI}></temba-flow-node>
    `);

    await node1Element.updateComplete;

    // Verify sortable list exists for internal drag (reordering within same node)
    const sortableList = node1Element.querySelector('temba-sortable-list');
    expect(sortableList).to.exist;

    // Verify it has external drag enabled
    expect(sortableList.hasAttribute('externaldrag')).to.be.true;
  });

  it('should only accept drops on execute_actions nodes', async () => {
    const routerNodeUI: NodeUI = {
      position: { left: 100, top: 100 },
      type: 'split_by_expression', // Not execute_actions
      config: {}
    };

    const routerNode: Node = {
      uuid: 'router-node',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: null }],
      router: {
        type: 'switch',
        operand: '@input',
        cases: [],
        categories: [],
        default_category_uuid: 'cat-1'
      }
    };

    const routerElement = await fixture<CanvasNode>(html`
      <temba-flow-node
        .node=${routerNode}
        .ui=${routerNodeUI}
      ></temba-flow-node>
    `);

    await routerElement.updateComplete;

    // Try to drag over a non-execute_actions node
    const dragOverEvent = new CustomEvent('action-drag-over', {
      detail: {
        action: node1.actions[0],
        sourceNodeUuid: 'node-1',
        actionIndex: 0,
        mouseY: 150
      },
      bubbles: false
    });
    routerElement.dispatchEvent(dragOverEvent);
    await routerElement.updateComplete;

    // Verify external drag info was NOT stored (rejected due to wrong node type)
    const externalDragInfo = (routerElement as any).externalDragInfo;
    expect(externalDragInfo).to.be.null;
  });
});
