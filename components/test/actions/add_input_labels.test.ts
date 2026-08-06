import { expect } from '@open-wc/testing';
import { add_input_labels } from '../../src/flow/actions/add_input_labels';
import { AddInputLabels } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the add_input_labels action configuration.
 */
describe('add_input_labels action config', () => {
  const helper = new ActionTest(add_input_labels, 'add_input_labels');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(add_input_labels.name).to.equal('Add Input Labels');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'add_input_labels',
        labels: [{ uuid: 'label-1', name: 'Important' }]
      } as AddInputLabels,
      'single-label'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'add_input_labels',
        labels: [
          { uuid: 'label-1', name: 'Important' },
          { uuid: 'label-2', name: 'Follow Up' },
          { uuid: 'label-3', name: 'Spam' }
        ]
      } as AddInputLabels,
      'multiple-labels'
    );
  });

  describe('metadata stripping', () => {
    it('should strip superfluous API metadata from labels', () => {
      const formData = {
        uuid: 'test-uuid',
        labels: [
          { uuid: 'label-1', name: 'Important', count: 250 },
          { uuid: 'label-2', name: 'Follow Up', count: 42 }
        ]
      };

      const action = add_input_labels.fromFormData(formData) as AddInputLabels;

      expect(action.labels).to.have.lengthOf(2);
      expect(action.labels[0]).to.deep.equal({
        uuid: 'label-1',
        name: 'Important'
      });
      expect(action.labels[1]).to.deep.equal({
        uuid: 'label-2',
        name: 'Follow Up'
      });
    });
  });
});
