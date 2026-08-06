import { expect } from '@open-wc/testing';
import { set_contact_field } from '../../src/flow/actions/set_contact_field';
import { SetContactField } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the set_contact_field action configuration.
 */
describe('set_contact_field action config', () => {
  const helper = new ActionTest(set_contact_field, 'set_contact_field');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(set_contact_field.name).to.equal('Update Field');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'set_contact_field',
        field: { key: 'favorite_color', name: 'Favorite Color' },
        value: 'Blue'
      } as SetContactField,
      'set-value'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'set_contact_field',
        field: { key: 'age', name: 'Age' },
        value: ''
      } as SetContactField,
      'clear-value'
    );
  });

  describe('metadata stripping', () => {
    it('should strip superfluous API metadata from field', () => {
      const formData = {
        uuid: 'test-uuid',
        field: [
          {
            key: 'favorite_color',
            name: 'Favorite Color',
            value_type: 'text',
            featured: true,
            usages: { campaign_events: 0, flows: 3, groups: 1 }
          }
        ],
        value: 'Red'
      };

      const action = set_contact_field.fromFormData(
        formData
      ) as SetContactField;

      expect(action.field).to.deep.equal({
        key: 'favorite_color',
        name: 'Favorite Color'
      });
    });
  });
});
