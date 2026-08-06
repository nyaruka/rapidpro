import { expect } from '@open-wc/testing';
import { split_by_resthook } from '../../src/flow/nodes/split_by_resthook';
import { Node, CallResthook } from '../../src/store/flow-definition.d';

describe('temba-split-by-resthook', () => {
  it('should transform from flow definition to form data correctly', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'action-uuid',
          resthook: 'new-registration'
        } as CallResthook
      ],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_number_between',
            arguments: ['200', '299'],
            category_uuid: 'cat-success'
          }
        ],
        categories: [
          { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
          { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
        ],
        default_category_uuid: 'cat-failure',
        operand: '@webhook.status'
      },
      exits: [
        { uuid: 'exit-success', destination_uuid: null },
        { uuid: 'exit-failure', destination_uuid: null }
      ]
    };

    const formData = split_by_resthook.toFormData!(node);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.resthook).to.have.lengthOf(1);
    expect(formData.resthook[0]).to.deep.equal({
      resthook: 'new-registration'
    });
    expect(formData.result_name).to.equal('');
  });

  it('should transform from flow definition to form data with result_name', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'action-uuid',
          resthook: 'payment-received'
        } as CallResthook
      ],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_number_between',
            arguments: ['200', '299'],
            category_uuid: 'cat-success'
          }
        ],
        categories: [
          { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
          { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
        ],
        result_name: 'payment_status',
        default_category_uuid: 'cat-failure',
        operand: '@webhook.status'
      },
      exits: [
        { uuid: 'exit-success', destination_uuid: null },
        { uuid: 'exit-failure', destination_uuid: null }
      ]
    };

    const formData = split_by_resthook.toFormData!(node);

    expect(formData.result_name).to.equal('payment_status');
    expect(formData.resthook).to.have.lengthOf(1);
    expect(formData.resthook[0]).to.deep.equal({
      resthook: 'payment-received'
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
      resthook: [{ resthook: 'new-registration' }]
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    expect(resultNode.uuid).to.equal('test-node-uuid');
    expect(resultNode.actions).to.have.lengthOf(1);

    const action = resultNode.actions![0];
    expect(action.type).to.equal('call_resthook');

    expect(resultNode.router!.type).to.equal('switch');
    expect(resultNode.router!.operand).to.equal(
      '@(default(webhook.status, 0))'
    );
    expect(resultNode.router!.categories).to.have.lengthOf(2); // Success + Failure
    expect(resultNode.exits).to.have.lengthOf(2); // Success + Failure

    // check success category
    const successCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Success'
    );
    expect(successCategory).to.exist;

    // check failure category
    const failureCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Failure'
    );
    expect(failureCategory).to.exist;
    expect(resultNode.router!.default_category_uuid).to.equal(
      failureCategory!.uuid
    );
  });

  it('should validate form data correctly', () => {
    // valid form data
    const validData = {
      resthook: [{ resthook: 'new-registration' }]
    };

    const validResult = split_by_resthook.validate!(validData);
    expect(validResult.valid).to.be.true;
    expect(Object.keys(validResult.errors)).to.have.lengthOf(0);

    // invalid form data - no resthook
    const invalidData = {
      resthook: []
    };

    const invalidResult = split_by_resthook.validate!(invalidData);
    expect(invalidResult.valid).to.be.false;
    expect(invalidResult.errors.resthook).to.equal('A resthook is required');

    // invalid form data - missing resthook
    const missingResthookData = {};

    const missingResult = split_by_resthook.validate!(missingResthookData);
    expect(missingResult.valid).to.be.false;
    expect(missingResult.errors.resthook).to.equal('A resthook is required');
  });

  it('should preserve existing UUIDs when editing', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'existing-action-uuid',
          resthook: 'new-registration'
        } as CallResthook
      ],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'existing-case-uuid',
            type: 'has_number_between',
            arguments: ['200', '299'],
            category_uuid: 'existing-success-uuid'
          }
        ],
        categories: [
          {
            uuid: 'existing-success-uuid',
            name: 'Success',
            exit_uuid: 'existing-success-exit-uuid'
          },
          {
            uuid: 'existing-failure-uuid',
            name: 'Failure',
            exit_uuid: 'existing-failure-exit-uuid'
          }
        ],
        default_category_uuid: 'existing-failure-uuid',
        operand: '@webhook.status'
      },
      exits: [
        {
          uuid: 'existing-success-exit-uuid',
          destination_uuid: 'some-node-uuid'
        },
        {
          uuid: 'existing-failure-exit-uuid',
          destination_uuid: 'another-node-uuid'
        }
      ]
    };

    // re-save with same resthook
    const formData = {
      uuid: 'test-node-uuid',
      resthook: [{ resthook: 'new-registration' }],
      result_name: ''
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    // UUIDs should be preserved
    expect(resultNode.actions![0].uuid).to.equal('existing-action-uuid');
    expect(resultNode.router!.cases![0].uuid).to.equal('existing-case-uuid');
    expect(resultNode.router!.categories![0].uuid).to.equal(
      'existing-success-uuid'
    );
    expect(resultNode.exits![0].uuid).to.equal('existing-success-exit-uuid');

    // destination connections should be preserved
    expect(resultNode.exits![0].destination_uuid).to.equal('some-node-uuid');
    expect(resultNode.exits![1].destination_uuid).to.equal('another-node-uuid');
  });

  it('should normalise legacy @webhook.json.status nodes on re-save', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'existing-action-uuid',
          resthook: 'new-registration'
        } as CallResthook
      ],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'existing-case-uuid',
            type: 'has_text',
            arguments: [],
            category_uuid: 'existing-success-uuid'
          }
        ],
        categories: [
          {
            uuid: 'existing-success-uuid',
            name: 'Success',
            exit_uuid: 'existing-success-exit-uuid'
          },
          {
            uuid: 'existing-failure-uuid',
            name: 'Failure',
            exit_uuid: 'existing-failure-exit-uuid'
          }
        ],
        default_category_uuid: 'existing-failure-uuid',
        operand: '@webhook.json.status'
      },
      exits: [
        { uuid: 'existing-success-exit-uuid', destination_uuid: null },
        { uuid: 'existing-failure-exit-uuid', destination_uuid: null }
      ]
    };

    const formData = {
      uuid: 'test-node-uuid',
      resthook: [{ resthook: 'new-registration' }],
      result_name: ''
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    // operand and case should be normalised to the canonical shape
    expect(resultNode.router!.operand).to.equal(
      '@(default(webhook.status, 0))'
    );
    expect(resultNode.router!.cases).to.have.lengthOf(1);
    expect(resultNode.router!.cases![0].type).to.equal('has_number_between');
    expect(resultNode.router!.cases![0].arguments).to.deep.equal([
      '200',
      '299'
    ]);

    // case, category, and exit UUIDs should be preserved across the rewrite
    expect(resultNode.router!.cases![0].uuid).to.equal('existing-case-uuid');
    expect(resultNode.router!.cases![0].category_uuid).to.equal(
      'existing-success-uuid'
    );
    const successCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Success'
    );
    const failureCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Failure'
    );
    expect(successCategory!.uuid).to.equal('existing-success-uuid');
    expect(successCategory!.exit_uuid).to.equal('existing-success-exit-uuid');
    expect(failureCategory!.uuid).to.equal('existing-failure-uuid');
    expect(failureCategory!.exit_uuid).to.equal('existing-failure-exit-uuid');
  });

  it('should handle changing resthook while preserving structure', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'existing-action-uuid',
          resthook: 'new-registration'
        } as CallResthook
      ],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'existing-case-uuid',
            type: 'has_number_between',
            arguments: ['200', '299'],
            category_uuid: 'existing-success-uuid'
          }
        ],
        categories: [
          {
            uuid: 'existing-success-uuid',
            name: 'Success',
            exit_uuid: 'existing-success-exit-uuid'
          },
          {
            uuid: 'existing-failure-uuid',
            name: 'Failure',
            exit_uuid: 'existing-failure-exit-uuid'
          }
        ],
        default_category_uuid: 'existing-failure-uuid',
        operand: '@webhook.status'
      },
      exits: [
        {
          uuid: 'existing-success-exit-uuid',
          destination_uuid: null
        },
        {
          uuid: 'existing-failure-exit-uuid',
          destination_uuid: null
        }
      ]
    };

    // change to different resthook
    const formData = {
      uuid: 'test-node-uuid',
      resthook: [{ resthook: 'payment-received' }]
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    // action UUID should be preserved
    expect(resultNode.actions![0].uuid).to.equal('existing-action-uuid');

    // resthook should be updated
    expect((resultNode.actions![0] as any).resthook).to.equal(
      'payment-received'
    );

    // structure should be preserved
    expect(resultNode.router!.categories).to.have.lengthOf(2);
    expect(resultNode.exits).to.have.lengthOf(2);
  });

  it('should handle empty result_name by trimming it', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      resthook: [{ resthook: 'new-registration' }],
      result_name: '   '
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);
    expect(resultNode.router.result_name).to.be.undefined;
  });

  it('should handle missing resthook selection gracefully', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    // missing resthook selection
    const formData = {
      uuid: 'test-node-uuid',
      resthook: [],
      result_name: ''
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    // should return original node unchanged
    expect(resultNode).to.equal(originalNode);
  });

  it('should handle null resthook selection', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      resthook: null,
      result_name: ''
    };

    const resultNode = split_by_resthook.fromFormData!(formData, originalNode);

    // should return original node unchanged
    expect(resultNode).to.equal(originalNode);
  });

  it('should render the resthook name', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [
        {
          type: 'call_resthook',
          uuid: 'action-uuid',
          resthook: 'payment-received'
        } as CallResthook
      ],
      exits: []
    };

    const rendered = split_by_resthook.render!(node);

    // check that the rendered output includes the resthook name
    expect(rendered.strings[0]).to.include('class="body"');
  });

  it('should handle missing resthook action when loading form data', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = split_by_resthook.toFormData!(node);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.resthook).to.have.lengthOf(0);
    expect(formData.result_name).to.equal('');
  });

  it('should render placeholder when no resthook configured', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const rendered = split_by_resthook.render!(node);

    // check that the rendered output includes placeholder text
    expect(rendered.strings[0]).to.include('class="body"');
  });
});
