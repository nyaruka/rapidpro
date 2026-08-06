import { expect } from '@open-wc/testing';
import { zustand } from '../src/store/AppState';
import { Node, NodeUI } from '../src/store/flow-definition';

describe('AppState Node Sorting', () => {
  beforeEach(() => {
    // reset the store state before each test
    const state = zustand.getState();
    zustand.setState({
      ...state,
      flowDefinition: {
        language: 'en',
        localization: {},
        name: 'Test Flow',
        nodes: [],
        uuid: 'test-uuid',
        type: 'messaging' as const,
        revision: 1,
        spec_version: '14.3',
        _ui: {
          nodes: {},
          languages: []
        }
      }
    });
  });

  describe('addNode', () => {
    it('should sort nodes by position when adding nodes', () => {
      const state = zustand.getState();

      // add nodes in non-sorted order
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 100, top: 300 }, // middle
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 100, top: 100 }, // top
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 100, top: 500 }, // bottom
        type: 'send_msg'
      };

      // add in order: middle, top, bottom
      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      const nodes = zustand.getState().flowDefinition.nodes;

      // nodes should be sorted by y position (top to bottom)
      expect(nodes[0].uuid).to.equal('node-2'); // top: 100
      expect(nodes[1].uuid).to.equal('node-1'); // top: 300
      expect(nodes[2].uuid).to.equal('node-3'); // top: 500
    });

    it('should sort by x when y positions are the same', () => {
      const state = zustand.getState();

      // add nodes with same y but different x
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 300, top: 100 },
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 500, top: 100 },
        type: 'send_msg'
      };

      // add in order: middle, left, right
      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      const nodes = zustand.getState().flowDefinition.nodes;

      // nodes should be sorted by x position (left to right) since y is same
      expect(nodes[0].uuid).to.equal('node-2'); // left: 100
      expect(nodes[1].uuid).to.equal('node-1'); // left: 300
      expect(nodes[2].uuid).to.equal('node-3'); // left: 500
    });

    it('should handle complex sorting with mixed positions', () => {
      const state = zustand.getState();

      // create a grid of nodes
      // row 1: (100, 100), (200, 100)
      // row 2: (100, 200), (200, 200)

      const nodes = [
        {
          node: {
            uuid: 'node-1',
            actions: [],
            exits: [{ uuid: 'exit-1', destination_uuid: null }]
          },
          ui: { position: { left: 200, top: 200 }, type: 'send_msg' as const }
        },
        {
          node: {
            uuid: 'node-2',
            actions: [],
            exits: [{ uuid: 'exit-2', destination_uuid: null }]
          },
          ui: { position: { left: 100, top: 100 }, type: 'send_msg' as const }
        },
        {
          node: {
            uuid: 'node-3',
            actions: [],
            exits: [{ uuid: 'exit-3', destination_uuid: null }]
          },
          ui: { position: { left: 200, top: 100 }, type: 'send_msg' as const }
        },
        {
          node: {
            uuid: 'node-4',
            actions: [],
            exits: [{ uuid: 'exit-4', destination_uuid: null }]
          },
          ui: { position: { left: 100, top: 200 }, type: 'send_msg' as const }
        }
      ];

      // add in random order
      nodes.forEach((n) => state.addNode(n.node, n.ui));

      const sortedNodes = zustand.getState().flowDefinition.nodes;

      // expected order: (100,100), (200,100), (100,200), (200,200)
      expect(sortedNodes[0].uuid).to.equal('node-2'); // (100, 100)
      expect(sortedNodes[1].uuid).to.equal('node-3'); // (200, 100)
      expect(sortedNodes[2].uuid).to.equal('node-4'); // (100, 200)
      expect(sortedNodes[3].uuid).to.equal('node-1'); // (200, 200)
    });
  });

  describe('createNode', () => {
    it('should sort nodes after creating a new node', () => {
      const state = zustand.getState();

      // create nodes in non-sorted order
      const uuid1 = state.createNode('send_msg', { left: 300, top: 100 });
      const uuid2 = state.createNode('send_msg', { left: 100, top: 100 });
      const uuid3 = state.createNode('send_msg', { left: 200, top: 100 });

      const nodes = zustand.getState().flowDefinition.nodes;

      // nodes should be sorted by x position
      expect(nodes[0].uuid).to.equal(uuid2); // left: 100
      expect(nodes[1].uuid).to.equal(uuid3); // left: 200
      expect(nodes[2].uuid).to.equal(uuid1); // left: 300
    });
  });

  describe('removeNodes', () => {
    it('should maintain sorting after removing nodes', () => {
      const state = zustand.getState();

      // create nodes
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 200, top: 100 },
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 300, top: 100 },
        type: 'send_msg'
      };

      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      // remove middle node
      state.removeNodes(['node-2']);

      const nodes = zustand.getState().flowDefinition.nodes;

      // remaining nodes should still be sorted
      expect(nodes.length).to.equal(2);
      expect(nodes[0].uuid).to.equal('node-1'); // left: 100
      expect(nodes[1].uuid).to.equal('node-3'); // left: 300
    });

    it('should sort nodes after connection rerouting during removal', () => {
      const state = zustand.getState();

      // create a chain of nodes
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: 'node-2' }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 100, top: 300 },
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: 'node-3' }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 200, top: 200 },
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 300, top: 100 },
        type: 'send_msg'
      };

      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      // verify initial sorting
      let nodes = zustand.getState().flowDefinition.nodes;
      expect(nodes[0].uuid).to.equal('node-3'); // top: 100
      expect(nodes[1].uuid).to.equal('node-2'); // top: 200
      expect(nodes[2].uuid).to.equal('node-1'); // top: 300

      // remove middle node - should reroute connection
      state.removeNodes(['node-2']);

      nodes = zustand.getState().flowDefinition.nodes;

      // nodes should still be sorted
      expect(nodes.length).to.equal(2);
      expect(nodes[0].uuid).to.equal('node-3'); // top: 100
      expect(nodes[1].uuid).to.equal('node-1'); // top: 300

      // verify rerouting happened
      expect(nodes[1].exits[0].destination_uuid).to.equal('node-3');
    });
  });

  describe('updateCanvasPositions', () => {
    it('should re-sort nodes when positions change', () => {
      const state = zustand.getState();

      // create nodes in sorted order
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 100, top: 200 },
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 100, top: 300 },
        type: 'send_msg'
      };

      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      let nodes = zustand.getState().flowDefinition.nodes;
      expect(nodes[0].uuid).to.equal('node-1'); // top: 100
      expect(nodes[1].uuid).to.equal('node-2'); // top: 200
      expect(nodes[2].uuid).to.equal('node-3'); // top: 300

      // move node-1 to the bottom
      state.updateCanvasPositions({
        'node-1': { left: 100, top: 400 }
      });

      nodes = zustand.getState().flowDefinition.nodes;

      // nodes should be re-sorted
      expect(nodes[0].uuid).to.equal('node-2'); // top: 200
      expect(nodes[1].uuid).to.equal('node-3'); // top: 300
      expect(nodes[2].uuid).to.equal('node-1'); // top: 400
    });

    it('should handle multiple position updates at once', () => {
      const state = zustand.getState();

      // create nodes
      const node1: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI1: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 100, top: 200 },
        type: 'send_msg'
      };

      const node3: Node = {
        uuid: 'node-3',
        actions: [],
        exits: [{ uuid: 'exit-3', destination_uuid: null }]
      };
      const nodeUI3: NodeUI = {
        position: { left: 100, top: 300 },
        type: 'send_msg'
      };

      state.addNode(node1, nodeUI1);
      state.addNode(node2, nodeUI2);
      state.addNode(node3, nodeUI3);

      // swap positions of node-1 and node-3
      state.updateCanvasPositions({
        'node-1': { left: 100, top: 300 },
        'node-3': { left: 100, top: 100 }
      });

      const nodes = zustand.getState().flowDefinition.nodes;

      // nodes should be re-sorted
      expect(nodes[0].uuid).to.equal('node-3'); // top: 100
      expect(nodes[1].uuid).to.equal('node-2'); // top: 200
      expect(nodes[2].uuid).to.equal('node-1'); // top: 300
    });

    it('should not affect sticky notes when updating positions', () => {
      const state = zustand.getState();

      // create a node
      const node: Node = {
        uuid: 'node-1',
        actions: [],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      const nodeUI: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      state.addNode(node, nodeUI);

      // create a sticky note
      const stickyUuid = state.createStickyNote({ left: 200, top: 200 });

      // update positions for both
      state.updateCanvasPositions({
        'node-1': { left: 100, top: 300 },
        [stickyUuid]: { left: 200, top: 100 }
      });

      const flowDef = zustand.getState().flowDefinition;

      // verify node position was updated
      expect(flowDef._ui.nodes['node-1'].position.top).to.equal(300);

      // verify sticky position was updated
      expect(flowDef._ui.stickies[stickyUuid].position.top).to.equal(100);
    });
  });

  describe('edge cases', () => {
    it('should handle nodes with missing position data', () => {
      const state = zustand.getState();

      // manually create a flow definition with a node that has no UI data
      zustand.setState({
        ...zustand.getState(),
        flowDefinition: {
          language: 'en',
          localization: {},
          name: 'Test Flow',
          nodes: [
            {
              uuid: 'node-1',
              actions: [],
              exits: [{ uuid: 'exit-1', destination_uuid: null }]
            }
          ],
          uuid: 'test-uuid',
          type: 'messaging' as const,
          revision: 1,
          spec_version: '14.3',
          _ui: {
            nodes: {}, // no UI data for node-1
            languages: []
          }
        }
      });

      // add a node with position data
      const node2: Node = {
        uuid: 'node-2',
        actions: [],
        exits: [{ uuid: 'exit-2', destination_uuid: null }]
      };
      const nodeUI2: NodeUI = {
        position: { left: 100, top: 100 },
        type: 'send_msg'
      };

      // should not throw error
      expect(() => state.addNode(node2, nodeUI2)).to.not.throw();

      const nodes = zustand.getState().flowDefinition.nodes;
      expect(nodes.length).to.equal(2);
    });

    it('should handle empty nodes array', () => {
      const state = zustand.getState();

      // verify initial state is empty
      expect(zustand.getState().flowDefinition.nodes.length).to.equal(0);

      // try to remove nodes from empty flow - should not throw
      expect(() => state.removeNodes(['non-existent'])).to.not.throw();
    });
  });
});
