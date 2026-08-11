import { expect } from '@open-wc/testing';
import { zustand } from '../src/store/AppState';
import { Node, NodeUI } from '../src/store/flow-definition';

describe('AppState duplicateNodes', () => {
  beforeEach(() => {
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
          stickies: {},
          languages: []
        }
      },
      dirtyDate: null
    });
  });

  it('should create copies with new UUIDs', () => {
    const state = zustand.getState();
    const node: Node = {
      uuid: 'node-1',
      actions: [{ type: 'send_msg', uuid: 'action-1' }],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };
    const nodeUI: NodeUI = {
      position: { left: 100, top: 200 },
      type: 'send_msg'
    };
    state.addNode(node, nodeUI);

    const mapping = state.duplicateNodes(['node-1']);
    const result = zustand.getState();

    // Should have 2 nodes now
    expect(result.flowDefinition.nodes.length).to.equal(2);

    // New node UUID should differ
    const newUuid = mapping['node-1'];
    expect(newUuid).to.exist;
    expect(newUuid).to.not.equal('node-1');

    // New node should exist
    const newNode = result.flowDefinition.nodes.find((n) => n.uuid === newUuid);
    expect(newNode).to.exist;

    // Action UUID should be remapped
    expect(newNode.actions[0].uuid).to.not.equal('action-1');
    expect(mapping['action-1']).to.equal(newNode.actions[0].uuid);

    // Exit UUID should be remapped
    expect(newNode.exits[0].uuid).to.not.equal('exit-1');
    expect(mapping['exit-1']).to.equal(newNode.exits[0].uuid);
  });

  it('should preserve internal connections between copied nodes', () => {
    const state = zustand.getState();

    const node1: Node = {
      uuid: 'node-1',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: 'node-2' }]
    };
    const node2: Node = {
      uuid: 'node-2',
      actions: [],
      exits: [{ uuid: 'exit-2', destination_uuid: null }]
    };

    state.addNode(node1, { position: { left: 0, top: 0 }, type: 'send_msg' });
    state.addNode(node2, {
      position: { left: 0, top: 200 },
      type: 'send_msg'
    });

    const mapping = state.duplicateNodes(['node-1', 'node-2']);
    const result = zustand.getState();

    const newNode1 = result.flowDefinition.nodes.find(
      (n) => n.uuid === mapping['node-1']
    );

    // Internal connection should point to the copied node-2
    expect(newNode1.exits[0].destination_uuid).to.equal(mapping['node-2']);
  });

  it('should sever external connections', () => {
    const state = zustand.getState();

    const node1: Node = {
      uuid: 'node-1',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: 'node-2' }]
    };
    const node2: Node = {
      uuid: 'node-2',
      actions: [],
      exits: [{ uuid: 'exit-2', destination_uuid: null }]
    };

    state.addNode(node1, { position: { left: 0, top: 0 }, type: 'send_msg' });
    state.addNode(node2, {
      position: { left: 0, top: 200 },
      type: 'send_msg'
    });

    // Only duplicate node-1 (node-2 is external)
    const mapping = state.duplicateNodes(['node-1']);
    const result = zustand.getState();

    const newNode1 = result.flowDefinition.nodes.find(
      (n) => n.uuid === mapping['node-1']
    );

    // External connection should be severed
    expect(newNode1.exits[0].destination_uuid).to.be.null;
  });

  it('should remap router category, case, and default_category UUIDs', () => {
    const state = zustand.getState();

    const splitNode: Node = {
      uuid: 'split-1',
      actions: [],
      exits: [
        { uuid: 'exit-yes', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ],
      router: {
        type: 'switch',
        operand: '@input.text',
        categories: [
          { uuid: 'cat-yes', name: 'Yes', exit_uuid: 'exit-yes' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        cases: [
          {
            uuid: 'case-1',
            type: 'has_any_word',
            arguments: ['yes'],
            category_uuid: 'cat-yes'
          }
        ],
        default_category_uuid: 'cat-other'
      }
    };

    state.addNode(splitNode, {
      position: { left: 0, top: 0 },
      type: 'split_by_expression' as any
    });

    const mapping = state.duplicateNodes(['split-1']);
    const result = zustand.getState();
    const newNode = result.flowDefinition.nodes.find(
      (n) => n.uuid === mapping['split-1']
    );

    // Category UUIDs remapped
    expect(newNode.router.categories[0].uuid).to.equal(mapping['cat-yes']);
    expect(newNode.router.categories[1].uuid).to.equal(mapping['cat-other']);

    // Category exit_uuids remapped
    expect(newNode.router.categories[0].exit_uuid).to.equal(
      mapping['exit-yes']
    );
    expect(newNode.router.categories[1].exit_uuid).to.equal(
      mapping['exit-other']
    );

    // Case UUIDs and category_uuid remapped
    expect(newNode.router.cases[0].uuid).to.equal(mapping['case-1']);
    expect(newNode.router.cases[0].category_uuid).to.equal(mapping['cat-yes']);

    // default_category_uuid remapped
    expect(newNode.router.default_category_uuid).to.equal(mapping['cat-other']);
  });

  it('should remap wait timeout category_uuid', () => {
    const state = zustand.getState();

    const waitNode: Node = {
      uuid: 'wait-1',
      actions: [],
      exits: [
        { uuid: 'exit-resp', destination_uuid: null },
        { uuid: 'exit-timeout', destination_uuid: null }
      ],
      router: {
        type: 'switch',
        categories: [
          { uuid: 'cat-resp', name: 'Response', exit_uuid: 'exit-resp' },
          { uuid: 'cat-timeout', name: 'Timeout', exit_uuid: 'exit-timeout' }
        ],
        default_category_uuid: 'cat-resp',
        wait: {
          type: 'msg',
          timeout: {
            category_uuid: 'cat-timeout',
            seconds: 60
          }
        }
      }
    };

    state.addNode(waitNode, {
      position: { left: 0, top: 0 },
      type: 'wait_for_response' as any
    });

    const mapping = state.duplicateNodes(['wait-1']);
    const result = zustand.getState();
    const newNode = result.flowDefinition.nodes.find(
      (n) => n.uuid === mapping['wait-1']
    );

    // wait.timeout.category_uuid should be remapped
    expect(newNode.router.wait.timeout.category_uuid).to.equal(
      mapping['cat-timeout']
    );
    expect(newNode.router.wait.timeout.category_uuid).to.not.equal(
      'cat-timeout'
    );
  });

  it('should copy localization entries for duplicated actions', () => {
    const state = zustand.getState();

    const node: Node = {
      uuid: 'node-1',
      actions: [
        { type: 'send_msg', uuid: 'action-1' } as any,
        { type: 'send_msg', uuid: 'action-2' } as any
      ],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };
    state.addNode(node, { position: { left: 0, top: 0 }, type: 'send_msg' });

    // Add localization
    state.updateLocalization('es', 'action-1', {
      text: ['Hola']
    });
    state.updateLocalization('fr', 'action-1', {
      text: ['Bonjour']
    });

    const mapping = state.duplicateNodes(['node-1']);
    const result = zustand.getState();

    // Spanish localization copied
    const esLoc = result.flowDefinition.localization['es'];
    expect(esLoc[mapping['action-1']]).to.deep.equal({ text: ['Hola'] });

    // French localization copied
    const frLoc = result.flowDefinition.localization['fr'];
    expect(frLoc[mapping['action-1']]).to.deep.equal({ text: ['Bonjour'] });

    // Original still intact
    expect(esLoc['action-1']).to.deep.equal({ text: ['Hola'] });
  });

  it('should duplicate sticky notes', () => {
    const state = zustand.getState();
    const stickyUuid = state.createStickyNote({ left: 100, top: 100 });

    // Update the sticky with content
    state.updateStickyNote(stickyUuid, {
      position: { left: 100, top: 100 },
      title: 'My Note',
      body: 'Some content',
      color: 'blue'
    });

    const mapping = state.duplicateNodes([stickyUuid]);
    const result = zustand.getState();
    const stickies = result.flowDefinition._ui.stickies;

    const newUuid = mapping[stickyUuid];
    expect(newUuid).to.exist;
    expect(newUuid).to.not.equal(stickyUuid);

    // Cloned sticky should have the same content
    expect(stickies[newUuid].title).to.equal('My Note');
    expect(stickies[newUuid].body).to.equal('Some content');
    expect(stickies[newUuid].color).to.equal('blue');

    // Original still intact
    expect(stickies[stickyUuid].title).to.equal('My Note');
  });

  it('should duplicate a mix of nodes and stickies', () => {
    const state = zustand.getState();

    const node: Node = {
      uuid: 'node-1',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };
    state.addNode(node, { position: { left: 0, top: 0 }, type: 'send_msg' });
    const stickyUuid = state.createStickyNote({ left: 200, top: 0 });

    const mapping = state.duplicateNodes(['node-1', stickyUuid]);
    const result = zustand.getState();

    expect(result.flowDefinition.nodes.length).to.equal(2);
    expect(Object.keys(result.flowDefinition._ui.stickies).length).to.equal(2);
    expect(mapping['node-1']).to.exist;
    expect(mapping[stickyUuid]).to.exist;
  });

  it('should not set dirtyDate', () => {
    const state = zustand.getState();

    const node: Node = {
      uuid: 'node-1',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };
    state.addNode(node, { position: { left: 0, top: 0 }, type: 'send_msg' });

    // Clear dirtyDate after addNode sets it
    zustand.setState({ ...zustand.getState(), dirtyDate: null });

    state.duplicateNodes(['node-1']);
    const result = zustand.getState();

    // duplicateNodes should not set dirtyDate
    expect(result.dirtyDate).to.be.null;
  });

  it('should preserve position of duplicated nodes', () => {
    const state = zustand.getState();

    const node: Node = {
      uuid: 'node-1',
      actions: [],
      exits: [{ uuid: 'exit-1', destination_uuid: null }]
    };
    state.addNode(node, {
      position: { left: 300, top: 400 },
      type: 'send_msg'
    });

    const mapping = state.duplicateNodes(['node-1']);
    const result = zustand.getState();

    const newNodeUI = result.flowDefinition._ui.nodes[mapping['node-1']];
    expect(newNodeUI.position.left).to.equal(300);
    expect(newNodeUI.position.top).to.equal(400);
  });
});
