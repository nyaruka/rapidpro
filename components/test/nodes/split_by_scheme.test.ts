import { expect } from '@open-wc/testing';
import { split_by_scheme } from '../../src/flow/nodes/split_by_scheme';
import { Node } from '../../src/store/flow-definition.d';

describe('temba-split-by-scheme', () => {
  it('should transform from flow definition to form data correctly', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_only_phrase',
            arguments: ['tel'],
            category_uuid: 'cat-1'
          },
          {
            uuid: 'case-2',
            type: 'has_only_phrase',
            arguments: ['facebook'],
            category_uuid: 'cat-2'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Phone', exit_uuid: 'exit-1' },
          { uuid: 'cat-2', name: 'Facebook', exit_uuid: 'exit-2' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@(urn_parts(contact.urn).scheme)',
        result_name: ''
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-2', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = split_by_scheme.toFormData!(node);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.schemes).to.have.lengthOf(2);
    expect(formData.schemes[0]).to.deep.equal({
      value: 'tel',
      name: 'SMS'
    });
    expect(formData.schemes[1]).to.deep.equal({
      value: 'facebook',
      name: 'Facebook'
    });
    expect(formData.result_name).to.equal('');
  });

  it('should transform from flow definition to form data with result_name', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_only_phrase',
            arguments: ['whatsapp'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'WhatsApp', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@(urn_parts(contact.urn).scheme)',
        result_name: 'channel_type'
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = split_by_scheme.toFormData!(node);

    expect(formData.result_name).to.equal('channel_type');
    expect(formData.schemes).to.have.lengthOf(1);
    expect(formData.schemes[0]).to.deep.equal({
      value: 'whatsapp',
      name: 'WhatsApp'
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
      schemes: [
        { value: 'tel', name: 'Phone' },
        { value: 'whatsapp', name: 'WhatsApp' }
      ],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    expect(resultNode.uuid).to.equal('test-node-uuid');
    expect(resultNode.router!.type).to.equal('switch');
    expect(resultNode.router!.operand).to.equal(
      '@(urn_parts(contact.urn).scheme)'
    );
    expect(resultNode.router!.cases).to.have.lengthOf(2);
    expect(resultNode.router!.categories).to.have.lengthOf(3); // 2 schemes + Other
    expect(resultNode.exits).to.have.lengthOf(3); // 2 schemes + Other

    // Check first scheme case
    const case1 = resultNode.router!.cases![0];
    expect(case1.type).to.equal('has_only_phrase');
    expect(case1.arguments).to.deep.equal(['tel']);

    // Check second scheme case
    const case2 = resultNode.router!.cases![1];
    expect(case2.type).to.equal('has_only_phrase');
    expect(case2.arguments).to.deep.equal(['whatsapp']);

    // Check categories match scheme names
    const telCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'SMS'
    );
    expect(telCategory).to.exist;

    const whatsappCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'WhatsApp'
    );
    expect(whatsappCategory).to.exist;

    // Check that "Other" category exists
    const otherCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Other'
    );
    expect(otherCategory).to.exist;
    expect(resultNode.router!.default_category_uuid).to.equal(
      otherCategory!.uuid
    );
  });

  it('should transform from form data with result_name', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      schemes: [{ value: 'telegram', name: 'Telegram' }],
      result_name: 'contact_channel'
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    expect(resultNode.router!.result_name).to.equal('contact_channel');
    expect(resultNode.router!.cases).to.have.lengthOf(1);
    expect(resultNode.router!.cases![0].arguments).to.deep.equal(['telegram']);
  });

  it('should handle string array format for schemes', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    // Test with plain string array (edge case)
    const formData = {
      uuid: 'test-node-uuid',
      schemes: ['email', 'twitter'],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    expect(resultNode.router!.cases).to.have.lengthOf(2);
    expect(resultNode.router!.cases![0].arguments).to.deep.equal(['email']);
    expect(resultNode.router!.cases![1].arguments).to.deep.equal(['twitter']);
  });

  it('should validate form data correctly', () => {
    // Valid form data
    const validData = {
      schemes: [{ value: 'tel', name: 'Phone' }]
    };

    const validResult = split_by_scheme.validate!(validData);
    expect(validResult.valid).to.be.true;
    expect(Object.keys(validResult.errors)).to.have.lengthOf(0);

    // Invalid form data - no schemes
    const invalidData = {
      schemes: []
    };

    const invalidResult = split_by_scheme.validate!(invalidData);
    expect(invalidResult.valid).to.be.false;
    expect(invalidResult.errors.schemes).to.equal(
      'At least one channel type is required'
    );

    // Invalid form data - missing schemes
    const missingSchemesData = {};

    const missingResult = split_by_scheme.validate!(missingSchemesData);
    expect(missingResult.valid).to.be.false;
    expect(missingResult.errors.schemes).to.equal(
      'At least one channel type is required'
    );
  });

  it('should preserve existing UUIDs when editing', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'existing-case-uuid',
            type: 'has_only_phrase',
            arguments: ['tel'],
            category_uuid: 'existing-cat-uuid'
          }
        ],
        categories: [
          {
            uuid: 'existing-cat-uuid',
            name: 'SMS',
            exit_uuid: 'existing-exit-uuid'
          },
          {
            uuid: 'existing-other-uuid',
            name: 'Other',
            exit_uuid: 'existing-other-exit-uuid'
          }
        ],
        default_category_uuid: 'existing-other-uuid',
        operand: '@(urn_parts(contact.urn).scheme)',
        result_name: ''
      },
      exits: [
        { uuid: 'existing-exit-uuid', destination_uuid: 'some-node-uuid' },
        {
          uuid: 'existing-other-exit-uuid',
          destination_uuid: 'another-node-uuid'
        }
      ]
    };

    // Re-save with same scheme
    const formData = {
      uuid: 'test-node-uuid',
      schemes: [{ value: 'tel', name: 'SMS' }],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    // UUIDs should be preserved
    expect(resultNode.router!.cases![0].uuid).to.equal('existing-case-uuid');
    expect(resultNode.router!.categories![0].uuid).to.equal(
      'existing-cat-uuid'
    );
    expect(resultNode.exits![0].uuid).to.equal('existing-exit-uuid');

    // Destination connections should be preserved
    expect(resultNode.exits![0].destination_uuid).to.equal('some-node-uuid');

    // Other category should be preserved
    const otherCategory = resultNode.router!.categories!.find(
      (cat) => cat.name === 'Other'
    );
    expect(otherCategory!.uuid).to.equal('existing-other-uuid');
    const otherExit = resultNode.exits!.find(
      (exit) => exit.uuid === otherCategory!.exit_uuid
    );
    expect(otherExit!.destination_uuid).to.equal('another-node-uuid');
  });

  it('should handle adding new schemes while preserving existing ones', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'existing-case-uuid',
            type: 'has_only_phrase',
            arguments: ['tel'],
            category_uuid: 'existing-cat-uuid'
          }
        ],
        categories: [
          {
            uuid: 'existing-cat-uuid',
            name: 'Phone',
            exit_uuid: 'existing-exit-uuid'
          },
          {
            uuid: 'existing-other-uuid',
            name: 'Other',
            exit_uuid: 'existing-other-exit-uuid'
          }
        ],
        default_category_uuid: 'existing-other-uuid',
        operand: '@(urn_parts(contact.urn).scheme)',
        result_name: ''
      },
      exits: [
        { uuid: 'existing-exit-uuid', destination_uuid: null },
        { uuid: 'existing-other-exit-uuid', destination_uuid: null }
      ]
    };

    // Add whatsapp to existing tel
    const formData = {
      uuid: 'test-node-uuid',
      schemes: [
        { value: 'tel', name: 'Phone' },
        { value: 'whatsapp', name: 'WhatsApp' }
      ],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    // Should have 2 cases now
    expect(resultNode.router!.cases).to.have.lengthOf(2);

    // First case (tel) should preserve UUID
    expect(resultNode.router!.cases![0].uuid).to.equal('existing-case-uuid');
    expect(resultNode.router!.cases![0].arguments).to.deep.equal(['tel']);

    // Second case (whatsapp) should have new UUID
    expect(resultNode.router!.cases![1].uuid).to.not.equal(
      'existing-case-uuid'
    );
    expect(resultNode.router!.cases![1].arguments).to.deep.equal(['whatsapp']);

    // Should have 3 categories (tel, whatsapp, Other)
    expect(resultNode.router!.categories).to.have.lengthOf(3);
  });

  it('should handle all supported scheme types', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const allSchemes = [
      'tel',
      'whatsapp',
      'facebook',
      'telegram',
      'twitter',
      'email',
      'viber',
      'line',
      'discord',
      'slack',
      'external'
    ];

    const formData = {
      uuid: 'test-node-uuid',
      schemes: allSchemes,
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    expect(resultNode.router!.cases).to.have.lengthOf(allSchemes.length);
    expect(resultNode.router!.categories).to.have.lengthOf(
      allSchemes.length + 1
    ); // +1 for Other

    // Verify all schemes are present
    allSchemes.forEach((scheme) => {
      const schemeCase = resultNode.router!.cases!.find(
        (c) => c.arguments![0] === scheme
      );
      expect(schemeCase).to.exist;
      expect(schemeCase!.type).to.equal('has_only_phrase');
    });
  });

  it('should handle unknown schemes gracefully', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_only_phrase',
            arguments: ['unknown_scheme'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'unknown_scheme', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@(urn_parts(contact.urn).scheme)',
        result_name: ''
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = split_by_scheme.toFormData!(node);

    // Should fall back to scheme code for unknown schemes
    expect(formData.schemes).to.have.lengthOf(1);
    expect(formData.schemes[0]).to.deep.equal({
      value: 'unknown_scheme',
      name: 'unknown_scheme'
    });
  });

  it('should properly set the operand', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      schemes: [{ value: 'tel', name: 'Phone' }],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    expect(resultNode.router!.operand).to.equal(
      '@(urn_parts(contact.urn).scheme)'
    );
  });

  it('should filter out empty or invalid schemes', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      schemes: [
        { value: 'tel', name: 'Phone' },
        null,
        undefined,
        { value: 'whatsapp', name: 'WhatsApp' }
      ],
      result_name: ''
    };

    const resultNode = split_by_scheme.fromFormData!(formData, originalNode);

    // Should only have 2 valid schemes
    expect(resultNode.router!.cases).to.have.lengthOf(2);
    expect(resultNode.router!.cases![0].arguments).to.deep.equal(['tel']);
    expect(resultNode.router!.cases![1].arguments).to.deep.equal(['whatsapp']);
  });
});
