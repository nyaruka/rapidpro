import { expect } from '@open-wc/testing';
import { set_run_result } from '../../src/flow/actions/set_run_result';
import { SetRunResult } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the set_run_result action configuration.
 */
describe('set_run_result action config', () => {
  const helper = new ActionTest(set_run_result, 'set_run_result');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(set_run_result.name).to.equal('Save Flow Result');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'set_run_result',
        name: 'Score',
        value: '100',
        category: 'High'
      } as SetRunResult,
      'with-category'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'set_run_result',
        name: 'Response',
        value: '@input.text',
        category: ''
      } as SetRunResult,
      'expression-value'
    );
  });

  describe('round-trip', () => {
    it('should extract name from select option array', () => {
      const formData = {
        uuid: 'test-uuid',
        name: [{ value: 'Score', name: 'Score' }],
        value: '42',
        category: 'Medium'
      };

      const action = set_run_result.fromFormData(formData) as SetRunResult;

      expect(action.name).to.equal('Score');
      expect(action.value).to.equal('42');
      expect(action.category).to.equal('Medium');
      expect(action.type).to.equal('set_run_result');
    });
  });
});
