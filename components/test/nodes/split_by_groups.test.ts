import { expect } from '@open-wc/testing';
import { split_by_groups } from '../../src/flow/nodes/split_by_groups';
import { Node } from '../../src/store/flow-definition.d';

describe('temba-split-by-groups', () => {
  it('should transform from flow definition to form data correctly', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_group',
            arguments: ['group-uuid-1', 'Group 1'],
            category_uuid: 'cat-1'
          },
          {
            uuid: 'case-2',
            type: 'has_group',
            arguments: ['group-uuid-2', 'Group 2'],
            category_uuid: 'cat-2'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Group 1', exit_uuid: 'exit-1' },
          { uuid: 'cat-2', name: 'Group 2', exit_uuid: 'exit-2' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@contact.groups',
        result_name: ''
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-2', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = split_by_groups.toFormData!(node);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.groups).to.have.lengthOf(2);
    expect(formData.groups[0]).to.deep.equal({
      uuid: 'group-uuid-1',
      name: 'Group 1'
    });
    expect(formData.groups[1]).to.deep.equal({
      uuid: 'group-uuid-2',
      name: 'Group 2'
    });
  });

  it('should transform from form data to flow definition correctly', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      groups: [
        { uuid: 'group-uuid-1', name: 'Group 1' },
        { uuid: 'group-uuid-2', name: 'Group 2' }
      ]
    };

    const resultNode = split_by_groups.fromFormData!(formData, originalNode);

    expect(resultNode.uuid).to.equal('test-node-uuid');
    expect(resultNode.router!.type).to.equal('switch');
    expect(resultNode.router!.operand).to.equal('@contact.groups');
    expect(resultNode.router!.cases).to.have.lengthOf(2);
    expect(resultNode.router!.categories).to.have.lengthOf(3); // 2 groups + Other
    expect(resultNode.exits).to.have.lengthOf(3); // 2 groups + Other

    // Check first group case
    const case1 = resultNode.router!.cases![0];
    expect(case1.type).to.equal('has_group');
    expect(case1.arguments).to.deep.equal(['group-uuid-1', 'Group 1']);

    // Check that "Other" category exists
    const otherCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Other'
    );
    expect(otherCategory).to.exist;
    expect(resultNode.router!.default_category_uuid).to.equal(
      otherCategory!.uuid
    );
  });

  it('should validate form data correctly', () => {
    // Valid form data
    const validData = {
      groups: [{ uuid: 'group-uuid-1', name: 'Group 1' }]
    };

    const validResult = split_by_groups.validate!(validData);
    expect(validResult.valid).to.be.true;
    expect(Object.keys(validResult.errors)).to.have.lengthOf(0);

    // Invalid form data - no groups
    const invalidData = {
      groups: []
    };

    const invalidResult = split_by_groups.validate!(invalidData);
    expect(invalidResult.valid).to.be.false;
    expect(invalidResult.errors.groups).to.equal(
      'At least one group is required'
    );

    // Invalid form data - missing groups
    const missingGroupsData = {};

    const missingResult = split_by_groups.validate!(missingGroupsData);
    expect(missingResult.valid).to.be.false;
    expect(missingResult.errors.groups).to.equal(
      'At least one group is required'
    );
  });

  it('should preserve category UUIDs when group names change only in casing', () => {
    // Group name is renamed from "Leads" to "LEADS" — the category should
    // keep its UUID and destination rather than being treated as a new one.
    const originalNode: Node = {
      uuid: 'node-1',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_group',
            arguments: ['group-1', 'Leads'],
            category_uuid: 'cat-existing'
          }
        ],
        categories: [
          { uuid: 'cat-existing', name: 'Leads', exit_uuid: 'exit-existing' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@contact.groups'
      },
      exits: [
        { uuid: 'exit-existing', destination_uuid: 'downstream' },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = {
      uuid: 'node-1',
      groups: [{ uuid: 'group-1', name: 'LEADS' }]
    };

    const result = split_by_groups.fromFormData!(formData, originalNode);

    const leads = result.router!.categories!.find(
      (c) => c.name.toLowerCase() === 'leads'
    );
    expect(leads).to.exist;
    expect(leads!.uuid).to.equal('cat-existing');
    expect(leads!.exit_uuid).to.equal('exit-existing');

    const preservedExit = result.exits!.find((e) => e.uuid === 'exit-existing');
    expect(preservedExit!.destination_uuid).to.equal('downstream');
  });

  it('should handle arbitrary groups correctly', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      groups: [
        { uuid: 'group-uuid-1', name: 'Existing Group' },
        { name: 'New Group', arbitrary: true }
      ]
    };

    const resultNode = split_by_groups.fromFormData!(formData, originalNode);

    expect(resultNode.router!.cases).to.have.lengthOf(2);

    // Check existing group
    const existingGroupCase = resultNode.router!.cases!.find(
      (c) => c.arguments![0] === 'group-uuid-1'
    );
    expect(existingGroupCase).to.exist;
    expect(existingGroupCase!.arguments).to.deep.equal([
      'group-uuid-1',
      'Existing Group'
    ]);

    // Check arbitrary group (should have generated UUID)
    const arbitraryGroupCase = resultNode.router!.cases!.find(
      (c) => c.arguments![1] === 'New Group'
    );
    expect(arbitraryGroupCase).to.exist;
    expect(arbitraryGroupCase!.arguments![0]).to.match(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
    );
    expect(arbitraryGroupCase!.arguments![1]).to.equal('New Group');
  });
});
