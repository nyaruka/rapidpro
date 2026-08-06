import { assert } from '@open-wc/testing';
import { zustand } from '../src/store/AppState';

describe('AppState Language Reset', () => {
  beforeEach(() => {
    // Reset the store state before each test
    const state = zustand.getState();
    zustand.setState({
      ...state,
      languageCode: '',
      isTranslating: false,
      flowDefinition: null,
      flowInfo: null
    });
  });

  it('should reset language when loading a new flow', () => {
    const state = zustand.getState();

    // First, load an initial flow to establish state
    const initialFlowContents = {
      definition: {
        language: 'en',
        localization: {},
        name: 'Initial Flow',
        nodes: [],
        uuid: 'initial-uuid',
        type: 'messaging' as const,
        revision: 1,
        spec_version: '14.3',
        _ui: {
          nodes: {},
          languages: []
        }
      },
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      }
    };

    state.setFlowContents(initialFlowContents);

    // Simulate having a previous flow with localization
    state.setLanguageCode('es'); // User selected Spanish for localization
    assert.equal(zustand.getState().languageCode, 'es');
    assert.equal(zustand.getState().isTranslating, true); // Now translating from English to Spanish

    // Simulate loading a new flow with English as default
    const mockFlowContents = {
      definition: {
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
      },
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      }
    };

    state.setFlowContents(mockFlowContents);

    // The language should reset to the flow's default language
    assert.equal(
      zustand.getState().languageCode,
      'en',
      'Language should reset to flow default'
    );
    assert.equal(
      zustand.getState().isTranslating,
      false,
      'Should not be in translation mode'
    );
  });

  it('should set isTranslating correctly when languages differ', () => {
    const state = zustand.getState();

    // Load a flow with Spanish as default
    const mockFlowContents = {
      definition: {
        language: 'es',
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
      },
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      }
    };

    state.setFlowContents(mockFlowContents);

    // Should be in Spanish and not translating
    assert.equal(zustand.getState().languageCode, 'es');
    assert.equal(zustand.getState().isTranslating, false);

    // Now switch to English for localization
    state.setLanguageCode('en');
    assert.equal(zustand.getState().languageCode, 'en');
    assert.equal(
      zustand.getState().isTranslating,
      true,
      'Should be translating when language differs from flow default'
    );
  });

  it('should preserve flow default language when no previous language is set', () => {
    const state = zustand.getState();

    // Load a flow with French as default, no previous language set
    const mockFlowContents = {
      definition: {
        language: 'fr',
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
      },
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      }
    };

    state.setFlowContents(mockFlowContents);

    // Should use the flow's default language
    assert.equal(
      zustand.getState().languageCode,
      'fr',
      'Should use flow default language'
    );
    assert.equal(
      zustand.getState().isTranslating,
      false,
      'Should not be translating'
    );
  });

  it('should handle language switching after flow is loaded', () => {
    const state = zustand.getState();

    // Load a flow with English as default
    const mockFlowContents = {
      definition: {
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
      },
      info: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      }
    };

    state.setFlowContents(mockFlowContents);

    // Should start in English, not translating
    assert.equal(zustand.getState().languageCode, 'en');
    assert.equal(zustand.getState().isTranslating, false);

    // Switch to Spanish for localization
    state.setLanguageCode('es');
    assert.equal(zustand.getState().languageCode, 'es');
    assert.equal(zustand.getState().isTranslating, true);

    // Switch back to English
    state.setLanguageCode('en');
    assert.equal(zustand.getState().languageCode, 'en');
    assert.equal(zustand.getState().isTranslating, false);
  });
});

describe('AppState Sticky Note Creation', () => {
  beforeEach(() => {
    // Reset the store state before each test
    const state = zustand.getState();
    zustand.setState({
      ...state,
      languageCode: '',
      isTranslating: false,
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
      flowInfo: {
        results: [],
        dependencies: [],
        counts: { nodes: 0, languages: 1 },
        locals: []
      },
      dirtyDate: null
    });
  });

  it('should create a new sticky note with correct defaults', () => {
    const state = zustand.getState();

    const position = { left: 100, top: 200 };
    const stickyUuid = state.createStickyNote(position);

    // Verify UUID was returned
    assert.isString(stickyUuid);
    assert.isTrue(stickyUuid.length > 0);

    // Verify sticky was added to the flow definition
    const currentState = zustand.getState();
    const stickies = currentState.flowDefinition._ui.stickies;

    assert.property(stickies, stickyUuid);

    const createdSticky = stickies[stickyUuid];
    assert.deepEqual(createdSticky.position, position);
    assert.equal(createdSticky.title, '');
    assert.equal(createdSticky.body, '');
    assert.equal(createdSticky.color, 'yellow');

    // Verify dirty date was set
    assert.isNotNull(currentState.dirtyDate);
    assert.instanceOf(currentState.dirtyDate, Date);
  });

  it('should create multiple unique sticky notes', () => {
    const state = zustand.getState();

    const position1 = { left: 100, top: 200 };
    const position2 = { left: 300, top: 400 };

    const uuid1 = state.createStickyNote(position1);
    const uuid2 = state.createStickyNote(position2);

    // UUIDs should be different
    assert.notEqual(uuid1, uuid2);

    // Both stickies should exist
    const currentState = zustand.getState();
    const stickies = currentState.flowDefinition._ui.stickies;

    assert.property(stickies, uuid1);
    assert.property(stickies, uuid2);

    // Positions should be correct
    assert.deepEqual(stickies[uuid1].position, position1);
    assert.deepEqual(stickies[uuid2].position, position2);
  });

  it('should initialize stickies object if it does not exist', () => {
    // Set up state without stickies
    const state = zustand.getState();
    zustand.setState({
      ...state,
      flowDefinition: {
        ...state.flowDefinition,
        _ui: {
          ...state.flowDefinition._ui,
          stickies: undefined
        }
      }
    });

    const position = { left: 50, top: 75 };
    const stickyUuid = state.createStickyNote(position);

    // Verify stickies object was created
    const currentState = zustand.getState();
    assert.isObject(currentState.flowDefinition._ui.stickies);
    assert.property(currentState.flowDefinition._ui.stickies, stickyUuid);
  });
});
