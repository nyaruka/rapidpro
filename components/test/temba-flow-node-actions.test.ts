import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { stub, useFakeTimers } from 'sinon';
import { CanvasNode } from '../src/flow/CanvasNode';
import { CustomEventType } from '../src/interfaces';
import { zustand } from '../src/store/AppState';
import { loadStore } from './utils.test';

const sendMsg = (uuid: string, text = 'Hello') => ({
  uuid,
  type: 'send_msg',
  text
});

const flowNode = (overrides: any = {}) => ({
  uuid: 'node-1',
  actions: [sendMsg('action-1')],
  exits: [{ uuid: 'exit-1', destination_uuid: 'node-2' }],
  ...overrides
});

// a plumber that records the calls made against it
const fakePlumber = () => ({
  makeTarget: stub(),
  makeSource: stub(),
  connectIds: stub(),
  forgetNode: stub(),
  revalidate: stub(),
  removeNodeConnections: stub(),
  removeExitConnection: stub(),
  setConnectionRemovingState: stub()
});

describe('temba-flow-node actions', () => {
  let node: CanvasNode;
  // CanvasNode declares node/ui/plumber private, so tests wire them up
  // through a loosely typed alias for the same element
  let inner: any;
  let plumber: any;
  let updateNode: any;

  // updateNode is swapped for a spy, so keep the real one to put back
  const realUpdateNode = zustand.getState().updateNode;

  beforeEach(async () => {
    await loadStore();
    plumber = fakePlumber();
    updateNode = stub();
    zustand.setState({ updateNode } as any);

    node = (await fixture('<temba-flow-node></temba-flow-node>')) as CanvasNode;
    inner = node as any;
    inner.node = flowNode() as any;
    inner.ui = {
      type: 'execute_actions',
      position: { left: 0, top: 0 }
    } as any;
    inner.plumber = plumber as any;
    await node.updateComplete;
  });

  afterEach(() => {
    // note: no sinon restore() here, it would tear down the shared
    // window.fetch stub that utils.test installs for the whole run
    zustand.setState({ updateNode: realUpdateNode } as any);
  });

  const events = (type: CustomEventType) => {
    const seen: any[] = [];
    node.addEventListener(type, (e: any) => seen.push(e.detail));
    return seen;
  };

  describe('disconnectExit', () => {
    it('clears the destination and tells the plumber', () => {
      (node as any).disconnectExit(inner.node.exits[0]);

      expect(plumber.removeExitConnection.calledWith('exit-1')).to.equal(true);
      expect(updateNode.calledOnce).to.equal(true);

      const [uuid, updated] = updateNode.firstCall.args;
      expect(uuid).to.equal('node-1');
      expect(updated.exits[0].destination_uuid).to.equal(null);
    });

    it('clears any pending removal state', () => {
      (node as any).exitRemovingState.add('exit-1');
      (node as any).disconnectExit(inner.node.exits[0]);
      expect((node as any).exitRemovingState.has('exit-1')).to.equal(false);
      expect(
        plumber.setConnectionRemovingState.calledWith('exit-1', false)
      ).to.equal(true);
    });

    it('leaves the other exits untouched', () => {
      inner.node = flowNode({
        exits: [
          { uuid: 'exit-1', destination_uuid: 'node-2' },
          { uuid: 'exit-2', destination_uuid: 'node-3' }
        ]
      }) as any;
      (node as any).disconnectExit(inner.node.exits[0]);
      const updated = updateNode.firstCall.args[1];
      expect(updated.exits[1].destination_uuid).to.equal('node-3');
    });
  });

  describe('removeAction', () => {
    it('removes one action of several', () => {
      inner.node = flowNode({
        actions: [sendMsg('action-1'), sendMsg('action-2')]
      }) as any;

      (node as any).removeAction(inner.node.actions[0], 0);

      expect(updateNode.calledOnce).to.equal(true);
      const updated = updateNode.firstCall.args[1];
      expect(updated.actions).to.have.length(1);
      expect(updated.actions[0].uuid).to.equal('action-2');
    });

    it('deletes the whole node when the last action goes', () => {
      const deleted = events(CustomEventType.NodeDeleted);
      (node as any).removeAction(inner.node.actions[0], 0);

      expect(deleted).to.have.length(1);
      expect(deleted[0].uuid).to.equal('node-1');
      expect(updateNode.called).to.equal(false);
    });

    it('clears any pending removal state', () => {
      inner.node = flowNode({
        actions: [sendMsg('action-1'), sendMsg('action-2')]
      }) as any;
      (node as any).actionRemovingState.add('action-1');
      (node as any).removeAction(inner.node.actions[0], 0);
      expect((node as any).actionRemovingState.has('action-1')).to.equal(false);
    });
  });

  describe('removeNode', () => {
    it('fires a node deleted event', () => {
      const deleted = events(CustomEventType.NodeDeleted);
      (node as any).removeNode();
      expect(deleted).to.have.length(1);
      expect(deleted[0].uuid).to.equal('node-1');
    });
  });

  describe('handleNodeRemoveClick', () => {
    const clickEvent = () =>
      new MouseEvent('click', { bubbles: true, cancelable: true });

    it('arms removal on the first click without deleting', () => {
      const deleted = events(CustomEventType.NodeDeleted);
      (node as any).handleNodeRemoveClick(clickEvent());
      expect((node as any).actionRemovingState.has('node-1')).to.equal(true);
      expect(deleted).to.have.length(0);
    });

    it('deletes on the second click', () => {
      const deleted = events(CustomEventType.NodeDeleted);
      (node as any).handleNodeRemoveClick(clickEvent());
      (node as any).handleNodeRemoveClick(clickEvent());
      expect(deleted).to.have.length(1);
    });

    it('disarms after a second of inactivity', () => {
      const clock = useFakeTimers();
      try {
        (node as any).handleNodeRemoveClick(clickEvent());
        expect((node as any).actionRemovingState.has('node-1')).to.equal(true);
        clock.tick(1000);
        expect((node as any).actionRemovingState.has('node-1')).to.equal(false);
      } finally {
        clock.restore();
      }
    });
  });

  describe('handleActionClick', () => {
    const clickOn = (target?: HTMLElement) => {
      const event = new MouseEvent('click', { bubbles: true });
      if (target) {
        Object.defineProperty(event, 'target', { value: target });
      } else {
        Object.defineProperty(event, 'target', {
          value: document.createElement('div')
        });
      }
      return event;
    };

    it('requests editing of the clicked action', () => {
      const requested = events(CustomEventType.ActionEditRequested);
      (node as any).handleActionClick(clickOn(), inner.node.actions[0]);
      expect(requested).to.have.length(1);
      expect(requested[0].action.uuid).to.equal('action-1');
      expect(requested[0].nodeUuid).to.equal('node-1');
    });

    it('ignores clicks on the remove button', () => {
      const requested = events(CustomEventType.ActionEditRequested);
      const button = document.createElement('div');
      button.className = 'remove-button';
      (node as any).handleActionClick(clickOn(button), inner.node.actions[0]);
      expect(requested).to.have.length(0);
    });

    it('ignores clicks while the action is being removed', () => {
      const requested = events(CustomEventType.ActionEditRequested);
      (node as any).actionRemovingState.add('action-1');
      (node as any).handleActionClick(clickOn(), inner.node.actions[0]);
      expect(requested).to.have.length(0);
    });
  });

  describe('handleNodeEditClick', () => {
    const clickEvent = () => {
      const event = new MouseEvent('click', { bubbles: true });
      Object.defineProperty(event, 'target', {
        value: document.createElement('div')
      });
      return event;
    };

    it('does nothing for a node with no router', () => {
      const nodeEvents = events(CustomEventType.NodeEditRequested);
      const actionEvents = events(CustomEventType.ActionEditRequested);
      (node as any).handleNodeEditClick(clickEvent());
      expect(nodeEvents).to.have.length(0);
      expect(actionEvents).to.have.length(0);
    });

    it('opens the node editor for a router with no actions', () => {
      inner.node = flowNode({
        actions: [],
        router: { type: 'switch', categories: [] }
      }) as any;
      const nodeEvents = events(CustomEventType.NodeEditRequested);
      (node as any).handleNodeEditClick(clickEvent());
      expect(nodeEvents).to.have.length(1);
      expect(nodeEvents[0].node.uuid).to.equal('node-1');
    });

    it('opens the action editor for a router with exactly one action', () => {
      inner.node = flowNode({
        actions: [sendMsg('action-1')],
        router: { type: 'switch', categories: [] }
      }) as any;
      const actionEvents = events(CustomEventType.ActionEditRequested);
      const nodeEvents = events(CustomEventType.NodeEditRequested);
      (node as any).handleNodeEditClick(clickEvent());
      expect(actionEvents).to.have.length(1);
      expect(actionEvents[0].action.uuid).to.equal('action-1');
      expect(nodeEvents).to.have.length(0);
    });

    it('opens the node editor for a router with several actions', () => {
      inner.node = flowNode({
        actions: [sendMsg('action-1'), sendMsg('action-2')],
        router: { type: 'switch', categories: [] }
      }) as any;
      const nodeEvents = events(CustomEventType.NodeEditRequested);
      (node as any).handleNodeEditClick(clickEvent());
      expect(nodeEvents).to.have.length(1);
    });

    it('ignores clicks on the remove button', () => {
      inner.node = flowNode({
        actions: [],
        router: { type: 'switch', categories: [] }
      }) as any;
      const nodeEvents = events(CustomEventType.NodeEditRequested);
      const event = new MouseEvent('click', { bubbles: true });
      const button = document.createElement('div');
      button.className = 'remove-button';
      Object.defineProperty(event, 'target', { value: button });
      (node as any).handleNodeEditClick(event);
      expect(nodeEvents).to.have.length(0);
    });
  });

  describe('drag ghost and original', () => {
    // the node renders its own sortable list, so record calls on that one
    const watchSortable = () => {
      const calls: boolean[] = [];
      const sortable = node.querySelector('temba-sortable-list');
      expect(
        sortable,
        'expected the node to render a sortable list'
      ).to.not.equal(null);
      (sortable as any).setOriginalVisible = (visible: boolean) =>
        calls.push(visible);
      return calls;
    };

    it('toggles the original through the sortable list', () => {
      const calls = watchSortable();

      node.dispatchEvent(new CustomEvent('action-show-original'));
      node.dispatchEvent(new CustomEvent('action-hide-original'));

      expect(calls).to.deep.equal([true, false]);
    });

    it('restores the placeholder when hiding the only action', () => {
      watchSortable();

      node.dispatchEvent(new CustomEvent('action-show-original'));
      expect((node as any).showLastActionPlaceholder).to.equal(false);

      node.dispatchEvent(new CustomEvent('action-hide-original'));
      expect((node as any).showLastActionPlaceholder).to.equal(true);
    });

    it('leaves the placeholder off when other actions remain', async () => {
      inner.node = flowNode({
        actions: [sendMsg('action-1'), sendMsg('action-2')]
      }) as any;
      await node.updateComplete;
      watchSortable();

      node.dispatchEvent(new CustomEvent('action-hide-original'));
      expect((node as any).showLastActionPlaceholder).to.equal(false);
    });

    it('shows and hides the drag ghost', () => {
      const ghost = document.createElement('div');
      ghost.className = 'ghost';
      ghost.style.display = 'none';
      document.body.appendChild(ghost);

      try {
        node.dispatchEvent(new CustomEvent('action-show-ghost'));
        expect(ghost.style.display).to.equal('block');

        node.dispatchEvent(new CustomEvent('action-hide-ghost'));
        expect(ghost.style.display).to.equal('none');
      } finally {
        ghost.remove();
      }
    });

    it('copes with no ghost element on the page', () => {
      expect(document.querySelector('.ghost')).to.equal(null);
      // no throw is the assertion here
      node.dispatchEvent(new CustomEvent('action-show-ghost'));
      node.dispatchEvent(new CustomEvent('action-hide-ghost'));
    });
  });
});
