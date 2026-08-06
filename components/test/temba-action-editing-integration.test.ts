import { expect, fixture, html } from '@open-wc/testing';
import { CanvasNode } from '../src/flow/CanvasNode';
import { DragManager } from '../src/flow/DragManager';
import {
  AddToGroup,
  EnterFlow,
  SendMsg,
  Node
} from '../src/store/flow-definition';
import { CustomEventType } from '../src/interfaces';
import '../temba-modules';

describe('Action Editing Integration', () => {
  it('should handle complete action editing workflow', async () => {
    // Create a test node with a send_msg action
    const testNode: Node = {
      uuid: 'test-node',
      actions: [
        {
          type: 'send_msg',
          uuid: 'test-action',
          text: 'Hello world',
          quick_replies: []
        } as SendMsg
      ],
      exits: []
    };

    // Create EditorNode
    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 } }}
      ></temba-flow-node>
    `);

    await editorNode.updateComplete;

    // Verify action is rendered
    const actionElement = editorNode.querySelector('.action');
    expect(actionElement).to.exist;

    // Set up event listener to catch ActionEditRequested event
    let editRequestedEvent: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (event: CustomEvent) => {
        editRequestedEvent = event;
      }
    );

    // Simulate clicking on the action content (not the remove button)
    const actionContent = editorNode.querySelector(
      '.action-content'
    ) as HTMLElement;
    expect(actionContent).to.exist;

    // Simulate a click (mousedown followed by mouseup at same position)
    const mouseDownEvent = new MouseEvent('mousedown', {
      clientX: 100,
      clientY: 100,
      bubbles: true
    });
    const mouseUpEvent = new MouseEvent('mouseup', {
      clientX: 100,
      clientY: 100,
      bubbles: true
    });

    actionContent.dispatchEvent(mouseDownEvent);
    actionContent.dispatchEvent(mouseUpEvent);

    // Verify event was fired
    expect(editRequestedEvent).to.exist;
    expect(editRequestedEvent!.detail.action).to.deep.equal(
      testNode.actions[0]
    );
    expect(editRequestedEvent!.detail.nodeUuid).to.equal('test-node');
  });

  it('should ignore clicks on remove button', async () => {
    // Create a test node with a send_msg action
    const testNode: Node = {
      uuid: 'test-node',
      actions: [
        {
          type: 'send_msg',
          uuid: 'test-action',
          text: 'Hello world',
          quick_replies: []
        } as SendMsg
      ],
      exits: []
    };

    // Create EditorNode
    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 } }}
      ></temba-flow-node>
    `);

    await editorNode.updateComplete;

    // Set up event listener to catch ActionEditRequested event
    let editRequestedEvent: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (event: CustomEvent) => {
        editRequestedEvent = event;
      }
    );

    // Simulate clicking on the remove button
    const removeButton = editorNode.querySelector(
      '.remove-button'
    ) as HTMLElement;
    expect(removeButton).to.exist;

    removeButton.click();

    // Verify NO ActionEditRequested event was fired (only remove action handling)
    expect(editRequestedEvent).to.be.null;
  });

  it('should not open action editor when dragging beyond threshold', async () => {
    // Create a test node with a send_msg action
    const testNode: Node = {
      uuid: 'test-node',
      actions: [
        {
          type: 'send_msg',
          uuid: 'test-action',
          text: 'Hello world',
          quick_replies: []
        } as SendMsg
      ],
      exits: []
    };

    // Create EditorNode
    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 } }}
      ></temba-flow-node>
    `);

    await editorNode.updateComplete;

    // Set up event listener to catch ActionEditRequested event
    let editRequestedEvent: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (event: CustomEvent) => {
        editRequestedEvent = event;
      }
    );

    // Simulate a drag operation (mousedown followed by mouseup at different position beyond threshold)
    const actionContent = editorNode.querySelector(
      '.action-content'
    ) as HTMLElement;
    expect(actionContent).to.exist;

    const mouseDownEvent = new MouseEvent('mousedown', {
      clientX: 100,
      clientY: 100,
      bubbles: true
    });
    const mouseUpEvent = new MouseEvent('mouseup', {
      clientX: 110, // 10 pixels away, beyond the 5 pixel threshold
      clientY: 100,
      bubbles: true
    });

    actionContent.dispatchEvent(mouseDownEvent);
    actionContent.dispatchEvent(mouseUpEvent);

    // Verify NO ActionEditRequested event was fired because we dragged beyond threshold
    expect(editRequestedEvent).to.be.null;
  });

  it('should open action editor when clicking within threshold', async () => {
    // Create a test node with a send_msg action
    const testNode: Node = {
      uuid: 'test-node',
      actions: [
        {
          type: 'send_msg',
          uuid: 'test-action',
          text: 'Hello world',
          quick_replies: []
        } as SendMsg
      ],
      exits: []
    };

    // Create EditorNode
    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 } }}
      ></temba-flow-node>
    `);

    await editorNode.updateComplete;

    // Set up event listener to catch ActionEditRequested event
    let editRequestedEvent: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (event: CustomEvent) => {
        editRequestedEvent = event;
      }
    );

    // Simulate a small movement (mousedown followed by mouseup at position within threshold)
    const actionContent = editorNode.querySelector(
      '.action-content'
    ) as HTMLElement;
    expect(actionContent).to.exist;

    const mouseDownEvent = new MouseEvent('mousedown', {
      clientX: 100,
      clientY: 100,
      bubbles: true
    });
    const mouseUpEvent = new MouseEvent('mouseup', {
      clientX: 103, // 3 pixels away, within the 5 pixel threshold
      clientY: 102, // 2 pixels away
      bubbles: true
    });

    actionContent.dispatchEvent(mouseDownEvent);
    actionContent.dispatchEvent(mouseUpEvent);

    // Verify ActionEditRequested event was fired because we stayed within threshold
    expect(editRequestedEvent).to.exist;
    expect(editRequestedEvent!.detail.action).to.deep.equal(
      testNode.actions[0]
    );
    expect(editRequestedEvent!.detail.nodeUuid).to.equal('test-node');
  });

  it('clicking a linked pill navigates without opening the action editor', async () => {
    // Action that renders groups as clickable pills (.linked-pill).
    const testNode: Node = {
      uuid: 'test-node',
      actions: [
        {
          type: 'add_contact_groups',
          uuid: 'test-action',
          groups: [{ uuid: 'group-1', name: 'Customers' }]
        } as AddToGroup
      ],
      exits: []
    };

    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 } }}
      ></temba-flow-node>
    `);

    await editorNode.updateComplete;

    let editRequestedEvent: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (event: CustomEvent) => {
        editRequestedEvent = event;
      }
    );

    const pill = editorNode.querySelector('.linked-pill') as HTMLElement;
    expect(pill, 'pill should be rendered for add_contact_groups action').to
      .exist;

    // Real click on the pill: mousedown then mouseup at the same position,
    // bubbling up through the action element. The action's mousedown/mouseup
    // handlers must bail out so they don't queue an ActionEditRequested —
    // otherwise a pill click would both navigate AND open the action editor.
    pill.dispatchEvent(
      new MouseEvent('mousedown', {
        clientX: 100,
        clientY: 100,
        bubbles: true
      })
    );
    pill.dispatchEvent(
      new MouseEvent('mouseup', { clientX: 100, clientY: 100, bubbles: true })
    );

    expect(
      editRequestedEvent,
      'ActionEditRequested must not fire for pill clicks'
    ).to.be.null;

    // Independently verify the pill's own @click handler is wired and runs.
    // The handler calls preventDefault, so defaultPrevented tells us it
    // executed even though there is no temba-flow-editor ancestor in this
    // fixture to receive the actual navigation event.
    const clickEvent = new MouseEvent('click', {
      cancelable: true,
      bubbles: true
    });
    pill.dispatchEvent(clickEvent);
    expect(
      clickEvent.defaultPrevented,
      'pill @click handler must fire to drive navigation'
    ).to.be.true;
  });

  it('clicking a linked pill in a router node does not open the node editor', async () => {
    // split_by_subflow renders the flow link as a clickable pill inside the
    // router section. That pill bubbles to handleNodeMouseDown / MouseUp,
    // which must bail via isActiveLink.
    const testNode: Node = {
      uuid: 'subflow-node',
      actions: [
        {
          type: 'enter_flow',
          uuid: 'enter-action',
          flow: { uuid: 'flow-1', name: 'Onboarding' }
        } as EnterFlow
      ],
      router: { type: 'switch', categories: [] } as any,
      exits: []
    };

    const editorNode: CanvasNode = await fixture(html`
      <temba-flow-node
        .node=${testNode}
        .ui=${{ position: { left: 0, top: 0 }, type: 'split_by_subflow' }}
      ></temba-flow-node>
    `);
    await editorNode.updateComplete;

    let nodeEditRequested: CustomEvent | null = null;
    let actionEditRequested: CustomEvent | null = null;
    editorNode.addEventListener(
      CustomEventType.NodeEditRequested,
      (e: CustomEvent) => {
        nodeEditRequested = e;
      }
    );
    editorNode.addEventListener(
      CustomEventType.ActionEditRequested,
      (e: CustomEvent) => {
        actionEditRequested = e;
      }
    );

    const pill = editorNode.querySelector('.linked-pill') as HTMLElement;
    expect(pill, 'flow pill should render inside the router section').to.exist;

    pill.dispatchEvent(
      new MouseEvent('mousedown', { clientX: 50, clientY: 50, bubbles: true })
    );
    pill.dispatchEvent(
      new MouseEvent('mouseup', { clientX: 50, clientY: 50, bubbles: true })
    );

    expect(nodeEditRequested, 'NodeEditRequested must not fire for pill clicks')
      .to.be.null;
    expect(
      actionEditRequested,
      'ActionEditRequested must not fire for pill clicks'
    ).to.be.null;
  });

  it('DragManager.handleMouseDown bails out when target is a linked pill', () => {
    // Direct unit test for DragManager — clicking on a pill must not begin
    // a node drag, just like clicking on .exit or .linked-name.
    const fakeEditor: any = {
      isReadOnly: () => false,
      blurActiveContentEditable: () => {},
      selectedItems: new Set<string>(),
      currentDragItem: null,
      definition: {
        _ui: {
          nodes: { 'node-1': { position: { left: 0, top: 0 } } },
          stickies: {}
        }
      },
      querySelector: () => null
    };
    const dm = new DragManager(fakeEditor);

    const nodeEl = document.createElement('temba-flow-node');
    nodeEl.setAttribute('uuid', 'node-1');
    const pill = document.createElement('temba-label');
    pill.classList.add('linked-pill');
    nodeEl.appendChild(pill);
    document.body.appendChild(nodeEl);

    try {
      nodeEl.addEventListener('mousedown', (e) => dm.handleMouseDown(e));
      pill.dispatchEvent(
        new MouseEvent('mousedown', {
          clientX: 5,
          clientY: 5,
          bubbles: true
        })
      );
      expect(
        fakeEditor.currentDragItem,
        'pill mousedown must not set currentDragItem'
      ).to.be.null;
      expect(
        fakeEditor.selectedItems.size,
        'pill mousedown must not mutate selectedItems'
      ).to.equal(0);

      // Sanity check: a mousedown on a non-pill region of the same node
      // still initiates the drag, so the assertion above isn't trivially
      // true for the wrong reason.
      const plainTarget = document.createElement('div');
      nodeEl.appendChild(plainTarget);
      plainTarget.dispatchEvent(
        new MouseEvent('mousedown', {
          clientX: 5,
          clientY: 5,
          bubbles: true
        })
      );
      expect(
        fakeEditor.currentDragItem,
        'mousedown outside a pill should begin a drag'
      ).to.not.be.null;
    } finally {
      document.body.removeChild(nodeEl);
    }
  });
});
