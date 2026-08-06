import { expect } from '@open-wc/testing';
import { add_contact_groups } from '../../src/flow/actions/add_contact_groups';
import { AddToGroup } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the add_contact_groups action configuration.
 */
describe('add_contact_groups action config', () => {
  const helper = new ActionTest(add_contact_groups, 'add_contact_groups');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(add_contact_groups.name).to.equal('Add to Group');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'add_contact_groups',
        groups: [{ uuid: 'group-1', name: 'VIP Customers' }]
      } as AddToGroup,
      'single-group'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'add_contact_groups',
        groups: [
          { uuid: 'group-1', name: 'VIP Customers' },
          { uuid: 'group-2', name: 'Newsletter Subscribers' },
          { uuid: 'group-3', name: 'Beta Testers' }
        ]
      } as AddToGroup,
      'multiple-groups'
    );

    helper.testAction(
      {
        uuid: 'test-action-3',
        type: 'add_contact_groups',
        groups: [
          {
            uuid: 'group-1',
            name: 'Very Long Group Name That Might Wrap to Multiple Lines'
          },
          {
            uuid: 'group-2',
            name: 'Another Extremely Long Group Name for Testing Layout'
          }
        ]
      } as AddToGroup,
      'long-group-names'
    );

    helper.testAction(
      {
        uuid: 'test-action-4',
        type: 'add_contact_groups',
        groups: [
          { uuid: 'group-1', name: 'Sales Team' },
          { uuid: 'group-2', name: 'Marketing Team' },
          { uuid: 'group-3', name: 'Support Team' },
          { uuid: 'group-4', name: 'Development Team' },
          { uuid: 'group-5', name: 'QA Team' }
        ]
      } as AddToGroup,
      'many-groups'
    );

    helper.testAction(
      {
        uuid: 'test-action-5',
        type: 'add_contact_groups',
        groups: [
          { uuid: 'group-1', name: 'Customers - Premium Plan (Monthly)' },
          { uuid: 'group-2', name: 'Customers - Enterprise Plan (Annual)' },
          { uuid: 'group-3', name: 'Trial Users - 30 Day Free Trial' }
        ]
      } as AddToGroup,
      'descriptive-group-names'
    );
  });

  describe('metadata stripping', () => {
    it('should strip superfluous API metadata from groups', () => {
      const formData = {
        uuid: 'test-uuid',
        groups: [
          {
            uuid: 'group-1',
            name: 'VIP Customers',
            query: 'status = vip',
            status: 'ready',
            count: 150,
            system: false
          },
          {
            uuid: 'group-2',
            name: 'Beta Testers',
            query: null,
            status: 'ready',
            count: 45,
            system: false
          }
        ]
      };

      const action = add_contact_groups.fromFormData(formData) as AddToGroup;

      expect(action.groups).to.have.lengthOf(2);
      expect(action.groups[0]).to.deep.equal({
        uuid: 'group-1',
        name: 'VIP Customers'
      });
      expect(action.groups[1]).to.deep.equal({
        uuid: 'group-2',
        name: 'Beta Testers'
      });
    });
  });
});
