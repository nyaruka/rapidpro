import { expect } from '@open-wc/testing';
import { useFakeTimers } from 'sinon';
import { setDependencyResolver, zustand } from '../src/store/AppState';
import { resolveDependencyNames } from '../src/flow/dependencies';
import { mockGET, clearMockGets } from './utils.test';

const definition = (overrides: any = {}) => ({
  uuid: 'flow-1',
  name: 'Test Flow',
  language: 'eng',
  type: 'messaging' as const,
  revision: 1,
  spec_version: '14.3',
  localization: {},
  nodes: [],
  _ui: { nodes: {}, languages: [] },
  ...overrides
});

const info = (overrides: any = {}) => ({
  results: [],
  dependencies: [],
  counts: { nodes: 0, languages: 1 },
  locals: [],
  ...overrides
});

const nodeWithExit = (uuid: string, exitUuid: string) => ({
  uuid,
  actions: [],
  exits: [{ uuid: exitUuid, destination_uuid: null }]
});

describe('store/AppState actions', () => {
  const pristine = zustand.getState();

  beforeEach(() => {
    zustand.setState({
      flowDefinition: null,
      flowInfo: null,
      languageCode: '',
      isTranslating: false,
      activity: null,
      activityEndpoint: null,
      viewingRevision: false
    } as any);
  });

  afterEach(() => {
    clearMockGets();
    setDependencyResolver(null);
    zustand.setState(pristine as any);
  });

  const state = () => zustand.getState();

  describe('setFlowInfo', () => {
    it('records the info', () => {
      state().setFlowInfo(info({ counts: { nodes: 3, languages: 2 } }));
      expect(state().flowInfo.counts.nodes).to.equal(3);
    });

    it('indexes an action issue by its action', () => {
      state().setFlowInfo(
        info({
          issues: [
            {
              type: 'missing_dependency',
              node_uuid: 'node-1',
              action_uuid: 'action-1',
              description: 'missing'
            }
          ]
        })
      );
      expect(state().issuesByAction.get('action-1')).to.have.length(1);
      // an action issue is filed under the action rather than the node
      expect(state().issuesByNode.get('node-1')).to.equal(undefined);
    });

    it('indexes a node issue by its node', () => {
      state().setFlowInfo(
        info({
          issues: [
            {
              type: 'missing_dependency',
              node_uuid: 'node-1',
              action_uuid: null,
              description: 'missing'
            }
          ]
        })
      );
      expect(state().issuesByNode.get('node-1')).to.have.length(1);
    });

    it('groups several issues on the same node', () => {
      state().setFlowInfo(
        info({
          issues: [
            {
              type: 'a',
              node_uuid: 'node-1',
              action_uuid: null,
              description: ''
            },
            {
              type: 'b',
              node_uuid: 'node-1',
              action_uuid: null,
              description: ''
            }
          ]
        })
      );
      expect(state().issuesByNode.get('node-1')).to.have.length(2);
    });

    it('clears the issue maps when there are no issues', () => {
      state().setFlowInfo(info({ issues: [] }));
      expect(state().issuesByNode.size).to.equal(0);
      expect(state().issuesByAction.size).to.equal(0);
    });
  });

  describe('updateDependencyNames', () => {
    beforeEach(() => {
      zustand.setState({
        flowDefinition: definition({
          nodes: [
            {
              uuid: 'node-1',
              exits: [],
              actions: [
                {
                  type: 'add_contact_groups',
                  uuid: 'action-1',
                  groups: [{ uuid: 'group-1', name: 'Old group name' }]
                }
              ]
            }
          ]
        }),
        flowInfo: info({
          dependencies: [
            { type: 'group', uuid: 'group-1', name: 'Old group name' }
          ]
        }),
        dirtyDate: null
      } as any);
    });

    it('updates a registered reference throughout the definition', () => {
      state().updateDependencyNames([
        {
          type: 'group',
          uuid: 'group-1',
          name: 'Customers'
        }
      ]);

      const action = state().flowDefinition.nodes[0].actions[0] as any;
      expect(action.groups[0].name).to.equal('Customers');
      expect(state().flowInfo.dependencies[0].name).to.equal('Customers');
      expect(state().dirtyDate).to.equal(null);
    });

    it('ignores an asset outside the registered dependency interests', () => {
      const before = state().flowDefinition;
      state().updateDependencyNames([
        {
          type: 'group',
          uuid: 'group-2',
          name: 'Unrelated'
        }
      ]);

      expect(state().flowDefinition).to.equal(before);
      expect(state().flowInfo.dependencies).to.have.length(1);
    });

    it('updates several cached assets in one state change', () => {
      const flow = { uuid: 'flow-1', name: 'Old flow' };
      zustand.setState({
        flowDefinition: definition({
          nodes: [
            {
              uuid: 'node-1',
              exits: [],
              actions: [
                {
                  type: 'enter_flow',
                  uuid: 'action-2',
                  flow
                },
                ...(state().flowDefinition.nodes[0].actions as any[])
              ]
            }
          ]
        }),
        flowInfo: info({
          dependencies: [
            { type: 'flow', uuid: 'flow-1', name: 'Old flow' },
            { type: 'group', uuid: 'group-1', name: 'Old group name' }
          ]
        }),
        dirtyDate: null
      } as any);

      state().updateDependencyNames([
        { type: 'flow', uuid: 'flow-1', name: 'Current flow' },
        { type: 'group', uuid: 'group-1', name: 'Customers' }
      ]);

      const actions = state().flowDefinition.nodes[0].actions as any[];
      expect(actions[0].flow.name).to.equal('Current flow');
      expect(actions[1].groups[0].name).to.equal('Customers');
      expect(state().dirtyDate).to.equal(null);
    });
  });

  describe('setRevision', () => {
    it('updates the revision on the definition', () => {
      zustand.setState({ flowDefinition: definition() } as any);
      state().setRevision(42);
      expect(state().flowDefinition.revision).to.equal(42);
    });
  });

  describe('getFlowResults and getResultByKey', () => {
    beforeEach(() => {
      zustand.setState({
        flowInfo: info({
          results: [
            {
              key: 'colour',
              name: 'Colour',
              categories: ['Red'],
              node_uuids: []
            },
            { key: 'size', name: 'Size', categories: ['Big'], node_uuids: [] }
          ]
        })
      } as any);
    });

    it('returns every result', () => {
      expect(state().getFlowResults()).to.have.length(2);
    });

    it('finds a result by its key', () => {
      expect(state().getResultByKey('size').name).to.equal('Size');
    });

    it('returns nothing for an unknown key', () => {
      expect(state().getResultByKey('nonsense')).to.equal(undefined);
    });
  });

  describe('getLanguage', () => {
    it('resolves the code to a display name', () => {
      zustand.setState({ languageCode: 'spa' } as any);
      // getLanguage is on the store but not declared on the AppState type
      const language = (state() as any).getLanguage();
      expect(language.code).to.equal('spa');
      expect(language.name).to.be.a('string');
      expect(language.name.length).to.be.greaterThan(0);
    });
  });

  describe('activity', () => {
    it('records the activity endpoint', () => {
      state().setActivityEndpoint('/flow/activity/flow-1/');
      expect(state().activityEndpoint).to.equal('/flow/activity/flow-1/');
    });

    it('replaces the current activity', () => {
      const activity = { nodes: { 'node-1': 3 }, segments: {} } as any;
      state().updateActivity(activity);
      expect(state().activity).to.deep.equal(activity);
    });

    it('reports simulator activity while the simulator is active', () => {
      const live = { nodes: { 'node-1': 1 }, segments: {} } as any;
      const simulated = { nodes: { 'node-2': 9 }, segments: {} } as any;
      state().updateActivity(live);
      state().updateSimulatorActivity(simulated);

      state().setSimulatorActive(false);
      expect(state().getCurrentActivity()).to.deep.equal(live);

      state().setSimulatorActive(true);
      expect(state().getCurrentActivity()).to.deep.equal(simulated);
    });
  });

  describe('updateConnection', () => {
    beforeEach(() => {
      zustand.setState({
        flowDefinition: definition({
          nodes: [nodeWithExit('node-1', 'exit-1')]
        })
      } as any);
    });

    it('points an exit at a destination', () => {
      state().updateConnection('node-1', 'exit-1', 'node-2');
      expect(
        state().flowDefinition.nodes[0].exits[0].destination_uuid
      ).to.equal('node-2');
      expect(state().dirtyDate).to.not.equal(null);
    });

    it('clears a destination', () => {
      state().updateConnection('node-1', 'exit-1', 'node-2');
      state().updateConnection('node-1', 'exit-1', null);
      expect(
        state().flowDefinition.nodes[0].exits[0].destination_uuid
      ).to.equal(null);
    });

    it('ignores an unknown node', () => {
      state().updateConnection('nonsense', 'exit-1', 'node-2');
      expect(
        state().flowDefinition.nodes[0].exits[0].destination_uuid
      ).to.equal(null);
    });

    it('ignores an unknown exit', () => {
      state().updateConnection('node-1', 'nonsense', 'node-2');
      expect(
        state().flowDefinition.nodes[0].exits[0].destination_uuid
      ).to.equal(null);
    });
  });

  describe('updateNodeUIConfig', () => {
    beforeEach(() => {
      zustand.setState({
        flowDefinition: definition({
          _ui: {
            nodes: {
              'node-1': {
                type: 'wait_for_response',
                position: { left: 0, top: 0 }
              }
            },
            languages: []
          }
        })
      } as any);
    });

    it('creates the config when there is none', () => {
      state().updateNodeUIConfig('node-1', { localizeRules: true });
      expect(
        state().flowDefinition._ui.nodes['node-1'].config.localizeRules
      ).to.equal(true);
    });

    it('merges into an existing config', () => {
      state().updateNodeUIConfig('node-1', { localizeRules: true });
      state().updateNodeUIConfig('node-1', { localizeCategories: true });
      const config = state().flowDefinition._ui.nodes['node-1'].config;
      expect(config.localizeRules).to.equal(true);
      expect(config.localizeCategories).to.equal(true);
    });

    it('updates the node type separately from the config', () => {
      state().updateNodeUIConfig('node-1', {
        type: 'split_by_expression',
        localizeRules: true
      });
      const nodeUI = state().flowDefinition._ui.nodes['node-1'];
      expect(nodeUI.type).to.equal('split_by_expression');
      expect(nodeUI.config.localizeRules).to.equal(true);
      // the type is not duplicated into the config
      expect(nodeUI.config.type).to.equal(undefined);
    });

    it('ignores an unknown node', () => {
      state().updateNodeUIConfig('nonsense', { localizeRules: true });
      expect(state().flowDefinition._ui.nodes['nonsense']).to.equal(undefined);
    });
  });

  describe('removeStickyNotes', () => {
    beforeEach(() => {
      zustand.setState({
        flowDefinition: definition({
          _ui: {
            nodes: {},
            languages: [],
            stickies: {
              'sticky-1': {
                title: 'One',
                body: '',
                position: { left: 0, top: 0 },
                color: 'yellow'
              },
              'sticky-2': {
                title: 'Two',
                body: '',
                position: { left: 0, top: 0 },
                color: 'blue'
              },
              'sticky-3': {
                title: 'Three',
                body: '',
                position: { left: 0, top: 0 },
                color: 'gray'
              }
            }
          }
        })
      } as any);
    });

    it('removes a single note', () => {
      state().removeStickyNotes(['sticky-2']);
      const stickies = state().flowDefinition._ui.stickies;
      expect(Object.keys(stickies)).to.deep.equal(['sticky-1', 'sticky-3']);
    });

    it('removes several notes at once', () => {
      state().removeStickyNotes(['sticky-1', 'sticky-3']);
      expect(Object.keys(state().flowDefinition._ui.stickies)).to.deep.equal([
        'sticky-2'
      ]);
    });

    it('ignores unknown uuids', () => {
      state().removeStickyNotes(['nonsense']);
      expect(Object.keys(state().flowDefinition._ui.stickies)).to.have.length(
        3
      );
    });

    it('copes with a flow that has no stickies', () => {
      zustand.setState({ flowDefinition: definition() } as any);
      state().removeStickyNotes(['sticky-1']);
      expect(state().flowDefinition._ui.stickies).to.equal(undefined);
    });
  });

  describe('setTranslationFilters', () => {
    beforeEach(() => {
      zustand.setState({ flowDefinition: definition() } as any);
    });

    it('turns the category filter on', () => {
      state().setTranslationFilters({ categories: true });
      expect(
        state().flowDefinition._ui.translation_filters.categories
      ).to.equal(true);
    });

    it('turns the category filter back off', () => {
      state().setTranslationFilters({ categories: true });
      state().setTranslationFilters({ categories: false });
      expect(
        state().flowDefinition._ui.translation_filters.categories
      ).to.equal(false);
    });

    it('does nothing when the filter is unchanged', () => {
      state().setTranslationFilters({ categories: true });
      const before = state().dirtyDate;
      state().setTranslationFilters({ categories: true });
      expect(state().dirtyDate).to.equal(before);
    });

    it('ignores a flow with no ui', () => {
      zustand.setState({
        flowDefinition: { ...definition(), _ui: null }
      } as any);
      // no throw is the assertion here
      state().setTranslationFilters({ categories: true });
    });
  });

  describe('fetchRevision', () => {
    const REVISION_URL = '/flow/revisions/flow-1';

    const mockRevision = (overrides: any = {}) => {
      clearMockGets();
      mockGET(/\/flow\/revisions\/flow-1\//, {
        definition: definition({ language: 'fra' }),
        info: info({ counts: { nodes: 1, languages: 1 } }),
        ...overrides
      });
    };

    it('loads the latest revision by default', async () => {
      mockRevision();
      await state().fetchRevision(REVISION_URL);
      expect(state().flowDefinition.uuid).to.equal('flow-1');
      expect(state().viewingRevision).to.equal(false);
    });

    it('adopts the language of the loaded flow', async () => {
      mockRevision();
      await state().fetchRevision(REVISION_URL);
      expect(state().languageCode).to.equal('fra');
      expect(state().isTranslating).to.equal(false);
    });

    it('marks an explicit revision as being viewed', async () => {
      mockRevision();
      await state().fetchRevision(REVISION_URL, '12345');
      expect(state().viewingRevision).to.equal(true);
    });

    it('does not treat "latest" as viewing an older revision', async () => {
      mockRevision();
      await state().fetchRevision(REVISION_URL, 'latest');
      expect(state().viewingRevision).to.equal(false);
    });

    it('indexes any issues that come back', async () => {
      mockRevision({
        info: info({
          issues: [
            {
              type: 'missing_dependency',
              node_uuid: 'node-9',
              action_uuid: null,
              description: 'missing'
            }
          ]
        })
      });
      await state().fetchRevision(REVISION_URL);
      expect(state().issuesByNode.get('node-9')).to.have.length(1);
    });

    it('resolves canonical dependency names before exposing a revision', async () => {
      const contactUuid = '22222222-2222-4222-8222-222222222222';
      let resolvedBeforeDisplay = false;
      setDependencyResolver(async () => {
        resolvedBeforeDisplay = state().flowDefinition === null;
        return [{ type: 'contact', uuid: contactUuid, name: 'Alice' }];
      });
      mockRevision({
        definition: definition({
          nodes: [
            {
              uuid: 'node-1',
              exits: [],
              actions: [
                {
                  type: 'send_broadcast',
                  uuid: 'action-1',
                  text: 'Hello',
                  contacts: [{ uuid: contactUuid, name: 'Old contact' }],
                  groups: []
                }
              ]
            }
          ],
          _ui: { nodes: { 'node-1': { position: { left: 0, top: 0 } } } }
        }),
        info: info({
          dependencies: [
            { type: 'contact', uuid: contactUuid, name: 'Old contact' }
          ]
        })
      });

      await state().fetchRevision(REVISION_URL);

      expect(resolvedBeforeDisplay).to.equal(true);
      expect(
        (state().flowDefinition.nodes[0].actions[0] as any).contacts[0].name
      ).to.equal('Alice');
      expect(state().flowInfo.dependencies[0].name).to.equal('Alice');
    });

    it('resolves every referenced flow before exposing a revision', async () => {
      const flow1Uuid = '11111111-1111-4111-8111-111111111111';
      const flow2Uuid = '22222222-2222-4222-8222-222222222222';
      let requested: any[] = [];
      setDependencyResolver(async (dependencies) => {
        requested = dependencies;
        return [
          { type: 'flow', uuid: flow1Uuid, name: 'Current Child One' },
          { type: 'flow', uuid: flow2Uuid, name: 'Current Child Two' }
        ];
      });
      mockRevision({
        definition: definition({
          nodes: [
            {
              uuid: 'node-1',
              exits: [],
              actions: [
                {
                  type: 'enter_flow',
                  uuid: 'action-1',
                  flow: { uuid: flow1Uuid, name: 'Old Child One' }
                },
                {
                  type: 'enter_flow',
                  uuid: 'action-2',
                  flow: { uuid: flow2Uuid, name: 'Old Child Two' }
                }
              ]
            }
          ],
          _ui: { nodes: { 'node-1': { position: { left: 0, top: 0 } } } }
        }),
        info: info({
          dependencies: [
            { type: 'flow', uuid: flow1Uuid, name: 'Old Child One' },
            { type: 'flow', uuid: flow2Uuid, name: 'Old Child Two' }
          ]
        })
      });

      await state().fetchRevision(REVISION_URL);

      expect(requested).to.deep.equal([
        { type: 'flow', uuid: flow1Uuid, name: 'Old Child One' },
        { type: 'flow', uuid: flow2Uuid, name: 'Old Child Two' }
      ]);
      const actions = state().flowDefinition.nodes[0].actions as any[];
      expect(actions[0].flow.name).to.equal('Current Child One');
      expect(actions[1].flow.name).to.equal('Current Child Two');
    });

    it('renders the flow when canonical names never arrive', async () => {
      let entered: () => void;
      const resolverEntered = new Promise<void>((resolve) => {
        entered = resolve;
      });
      const clock = useFakeTimers({ shouldAdvanceTime: true });
      try {
        // a resolver that hangs must not hold the editor hostage
        setDependencyResolver(() => {
          entered();
          return new Promise<any>(() => {});
        });
        mockRevision({
          definition: definition({
            nodes: [
              {
                uuid: 'node-1',
                exits: [],
                actions: [
                  {
                    type: 'add_contact_groups',
                    uuid: 'action-1',
                    groups: [{ uuid: 'group-1', name: 'Embedded name' }]
                  }
                ]
              }
            ],
            _ui: { nodes: { 'node-1': { position: { left: 0, top: 0 } } } }
          }),
          info: info({
            dependencies: [
              { type: 'group', uuid: 'group-1', name: 'Embedded name' }
            ]
          })
        });

        const pending = state().fetchRevision(REVISION_URL);
        // the timeout is armed as soon as the resolver is entered
        await resolverEntered;
        clock.tick(3100);
        await pending;

        expect(state().flowDefinition).to.not.equal(null);
        expect(
          (state().flowDefinition.nodes[0].actions[0] as any).groups[0].name
        ).to.equal('Embedded name');
      } finally {
        clock.restore();
      }
    });

    it('raises when the request fails', async () => {
      clearMockGets();
      mockGET(/\/flow\/revisions\/flow-1\//, { detail: 'boom' }, {}, '500');
      let raised = false;
      try {
        await state().fetchRevision(REVISION_URL);
      } catch (error) {
        raised = true;
      }
      expect(raised).to.equal(true);
    });
  });
});

describe('flow/dependencies resolveDependencyNames', () => {
  const withNodes = (nodes: any[]): any => ({
    uuid: 'flow-1',
    name: 'Test Flow',
    language: 'eng',
    type: 'messaging',
    revision: 1,
    spec_version: '14.3',
    localization: {},
    nodes,
    _ui: { nodes: {}, languages: [] }
  });

  it('rewrites a uuid reference wherever it appears', () => {
    const definition = withNodes([
      {
        uuid: 'node-1',
        exits: [],
        actions: [
          {
            type: 'add_contact_groups',
            uuid: 'action-1',
            groups: [{ uuid: 'group-1', name: 'Old' }]
          }
        ]
      }
    ]);

    const resolved: any = resolveDependencyNames(definition, [
      { type: 'group', uuid: 'group-1', name: 'Customers' }
    ]);

    expect(resolved.nodes[0].actions[0].groups[0].name).to.equal('Customers');
  });

  it('rewrites a reference whose embedded uuid is not canonical', () => {
    const uuid = '9de3663f-c5c5-4c92-9f45-ecbc09abcc85';
    const definition = withNodes([
      {
        uuid: 'node-1',
        exits: [],
        actions: [
          {
            type: 'add_contact_groups',
            uuid: 'action-1',
            groups: [
              // uppercase, braced and unhyphenated forms of the same uuid
              { uuid: uuid.toUpperCase(), name: 'Old' },
              { uuid: `{${uuid}}`, name: 'Old' },
              { uuid: uuid.replace(/-/g, ''), name: 'Old' }
            ]
          }
        ]
      }
    ]);

    // the dependency list carries the canonical form the server echoes back
    const resolved: any = resolveDependencyNames(definition, [
      { type: 'group', uuid, name: 'Customers' }
    ]);

    for (const group of resolved.nodes[0].actions[0].groups) {
      expect(group.name).to.equal('Customers');
    }
  });

  it('rewrites a keyed field reference under a field property', () => {
    const definition = withNodes([
      {
        uuid: 'node-1',
        exits: [],
        actions: [
          {
            type: 'set_contact_field',
            uuid: 'action-1',
            field: { key: 'age', name: 'Old age label' },
            value: '10'
          }
        ]
      }
    ]);

    const resolved: any = resolveDependencyNames(definition, [
      { type: 'field', key: 'age', name: 'Age' }
    ]);

    expect(resolved.nodes[0].actions[0].field.name).to.equal('Age');
  });

  it('rewrites keyed field references nested in an array', () => {
    const definition = withNodes([
      {
        uuid: 'node-1',
        exits: [],
        actions: [
          {
            type: 'set_contact_field',
            uuid: 'action-1',
            field: [{ key: 'age', name: 'Old age label' }]
          }
        ]
      }
    ]);

    const resolved: any = resolveDependencyNames(definition, [
      { type: 'field', key: 'age', name: 'Age' }
    ]);

    expect(resolved.nodes[0].actions[0].field[0].name).to.equal('Age');
  });

  it('leaves keyed structures outside a field property alone', () => {
    const definition = withNodes([
      {
        uuid: 'node-1',
        exits: [],
        actions: [],
        router: {
          type: 'switch',
          result_name: 'age',
          categories: [],
          // a keyed structure that happens to share the field key
          result: { key: 'age', name: 'Result label' }
        }
      }
    ]);

    const resolved: any = resolveDependencyNames(definition, [
      { type: 'field', key: 'age', name: 'Age' }
    ]);

    expect(resolved.nodes[0].router.result.name).to.equal('Result label');
  });

  it('returns the definition untouched when nothing is registered', () => {
    const definition = withNodes([]);
    expect(resolveDependencyNames(definition, [])).to.equal(definition);
  });
});
