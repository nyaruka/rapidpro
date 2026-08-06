import { expect } from '@open-wc/testing';
import { zustand } from '../src/store/AppState';
import { shouldExcludeFlow, hasLLMRole } from '../src/flow/flow-utils';

function setFlowType(type: string) {
  const state = zustand.getState();
  zustand.setState({
    ...state,
    flowDefinition: {
      language: 'en',
      localization: {},
      name: 'Test Flow',
      nodes: [],
      uuid: 'test-uuid',
      type: type as any,
      revision: 1,
      spec_version: '14.3',
      _ui: { nodes: {}, languages: [] }
    }
  });
}

describe('shouldExcludeFlow', () => {
  it('excludes message flows when current flow is background', () => {
    setFlowType('messaging_background');
    expect(shouldExcludeFlow({ type: 'message' })).to.be.true;
  });

  it('allows background flows when current flow is background', () => {
    setFlowType('messaging_background');
    expect(shouldExcludeFlow({ type: 'background' })).to.be.false;
  });

  it('allows message flows when current flow is messaging', () => {
    setFlowType('messaging');
    expect(shouldExcludeFlow({ type: 'message' })).to.be.false;
  });

  it('allows background flows when current flow is messaging', () => {
    setFlowType('messaging');
    expect(shouldExcludeFlow({ type: 'background' })).to.be.false;
  });

  it('returns false when flow definition is null', () => {
    zustand.setState({ ...zustand.getState(), flowDefinition: null });
    expect(shouldExcludeFlow({ type: 'message' })).to.be.false;
  });
});

describe('hasLLMRole', () => {
  it('returns true when the model has the role', () => {
    expect(hasLLMRole({ roles: ['engine'] }, 'engine')).to.be.true;
    expect(hasLLMRole({ roles: ['editing', 'engine'] }, 'editing')).to.be.true;
  });

  it('returns false when the model lacks the role', () => {
    expect(hasLLMRole({ roles: ['editing'] }, 'engine')).to.be.false;
    expect(hasLLMRole({ roles: ['engine'] }, 'editing')).to.be.false;
    expect(hasLLMRole({ roles: [] }, 'engine')).to.be.false;
  });
});
