import { expect } from '@open-wc/testing';
import { split_by_contact_field } from '../../src/flow/nodes/split_by_contact_field';
import { Node } from '../../src/store/flow-definition';

describe('split_by_contact_field', () => {
  it('should have correct configuration', () => {
    expect(split_by_contact_field.type).to.equal('split_by_contact_field');
    expect(split_by_contact_field.name).to.equal('Split by Contact Field');
    expect(split_by_contact_field.dialogSize).to.equal('large');
  });

  it('should have field select configuration', () => {
    const fieldConfig = split_by_contact_field.form!.field as any;
    expect(fieldConfig).to.exist;
    expect(fieldConfig.type).to.equal('select');
    expect(fieldConfig.required).to.be.true;
    expect(fieldConfig.searchable).to.be.true;
    expect(fieldConfig.endpoint).to.equal('/api/v2/fields.json');
  });

  it('should provide system properties and URN schemes as options', () => {
    const fieldConfig = split_by_contact_field.form!.field as any;
    const options = fieldConfig.options;
    expect(options).to.exist;
    expect(Array.isArray(options)).to.be.true;

    // Should have 4 system properties + multiple URN schemes
    expect(options.length).to.be.greaterThan(4);

    // Check that system properties are present
    const names = options.map((opt: any) => opt.name);
    expect(names).to.include('Name');
    expect(names).to.include('Language');
    expect(names).to.include('Status');
    expect(names).to.include('Channel');

    // Check that some URN schemes are present
    expect(names).to.include('WhatsApp Number');
    expect(names).to.include('Facebook ID');
  });

  it('should have rules configuration', () => {
    expect(split_by_contact_field.form!.rules).to.exist;
    expect(split_by_contact_field.form!.rules.type).to.equal('array');
  });

  it('should have result_name configuration', () => {
    expect(split_by_contact_field.form!.result_name).to.exist;
    expect(split_by_contact_field.form!.result_name.type).to.equal('text');
    expect(split_by_contact_field.form!.result_name.required).to.be.false;
  });

  it('should validate that field is required', () => {
    const result = split_by_contact_field.validate!({});
    expect(result.valid).to.be.false;
    expect(result.errors).to.have.property('field');
  });

  it('should validate successfully with a field', () => {
    const result = split_by_contact_field.validate!({
      field: [{ id: 'name', name: 'Name', type: 'property' }]
    });
    expect(result.valid).to.be.true;
    expect(Object.keys(result.errors).length).to.equal(0);
  });

  it('should transform from flow definition to form data for system property', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_text',
            arguments: ['John'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'John', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@contact.name',
        result_name: 'contact_name'
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const nodeUI = {
      type: 'split_by_contact_field',
      position: { left: 0, top: 0 },
      config: {
        operand: {
          id: 'name',
          name: 'Name',
          type: 'property'
        }
      }
    };

    const formData = split_by_contact_field.toFormData!(node, nodeUI);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.field).to.have.lengthOf(1);
    expect(formData.field[0].id).to.equal('name');
    expect(formData.field[0].name).to.equal('Name');
    expect(formData.field[0].type).to.equal('property');
    expect(formData.result_name).to.equal('contact_name');
  });

  it('should transform from flow definition to form data for custom field', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_text',
            arguments: ['red'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Red', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@fields.favorite_color',
        result_name: ''
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const nodeUI = {
      type: 'split_by_contact_field',
      position: { left: 0, top: 0 },
      config: {
        operand: {
          key: 'favorite_color',
          id: 'favorite_color',
          name: 'Favorite Color',
          type: 'field'
        }
      }
    };

    const formData = split_by_contact_field.toFormData!(node, nodeUI);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.field).to.have.lengthOf(1);
    expect(formData.field[0].key).to.equal('favorite_color');
    expect(formData.field[0].id).to.equal('favorite_color');
    expect(formData.field[0].name).to.equal('Favorite Color');
    expect(formData.field[0].type).to.equal('field');
    expect(formData.result_name).to.equal('');
  });

  it('should transform from form data to flow definition for system property', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [],
        categories: [],
        default_category_uuid: '',
        operand: '@input.text'
      },
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      field: [{ id: 'language', name: 'Language', type: 'property' }],
      rules: [
        {
          operator: 'has_only_phrase', // Requires 1 operand
          value1: 'eng',
          value2: '',
          category: 'English'
        }
      ],
      result_name: 'user_language'
    };

    const updatedNode = split_by_contact_field.fromFormData!(
      formData,
      originalNode
    );

    expect(updatedNode.router!.operand).to.equal('@contact.language');
    expect(updatedNode.router!.result_name).to.equal('user_language');

    // Should have at least an "Other" category from createRulesRouter
    expect(updatedNode.router!.categories.length).to.be.greaterThan(0);
    expect(updatedNode.exits.length).to.be.greaterThan(0);

    // Check if the case was created (it should be if the rule is valid)
    expect(updatedNode.router!.cases.length).to.be.greaterThan(0);
    expect(updatedNode.router!.cases[0].type).to.equal('has_only_phrase');
    expect(updatedNode.router!.cases[0].arguments).to.deep.equal(['eng']);
  });

  it('should transform from form data to flow definition for custom field', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [],
        categories: [],
        default_category_uuid: '',
        operand: '@input.text'
      },
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      field: [{ key: 'age', name: 'Age', type: 'field' }],
      rules: [
        {
          operator: { value: 'has_number_gte', name: 'has a number >= to' },
          value1: '18',
          value2: '',
          category: 'Adult'
        }
      ],
      result_name: ''
    };

    const updatedNode = split_by_contact_field.fromFormData!(
      formData,
      originalNode
    );

    expect(updatedNode.router!.operand).to.equal('@fields.age');
    expect(updatedNode.router!.result_name).to.be.undefined;
    expect(updatedNode.router!.cases.length).to.equal(1);
    expect(updatedNode.router!.cases[0].type).to.equal('has_number_gte');
  });

  it('should preserve existing exits when updating', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_text',
            arguments: ['red'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Red', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@fields.color'
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: 'next-node-uuid' },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const formData = {
      uuid: 'test-node-uuid',
      field: [{ key: 'color', name: 'Color', type: 'field' }],
      rules: [
        {
          operator: { value: 'has_text', name: 'has some text' },
          value1: 'blue',
          value2: '',
          category: 'Blue'
        }
      ],
      result_name: ''
    };

    const updatedNode = split_by_contact_field.fromFormData!(
      formData,
      originalNode
    );

    // Should have at least 2 exits (Blue and Other)
    expect(updatedNode.exits.length).to.be.at.least(2);

    // Check that the operand is correct
    expect(updatedNode.router!.operand).to.equal('@fields.color');
  });

  it('should generate UI config from form data for system property', () => {
    const formData = {
      field: [{ id: 'language', name: 'Language', type: 'property' }],
      rules: [],
      result_name: ''
    };

    const uiConfig = split_by_contact_field.toUIConfig!(formData);

    expect(uiConfig.operand).to.exist;
    expect(uiConfig.operand.id).to.equal('language');
    expect(uiConfig.operand.name).to.equal('Language');
    expect(uiConfig.operand.type).to.equal('property');
  });

  it('should generate UI config from form data for custom field', () => {
    const formData = {
      field: [
        {
          key: 'favorite_color',
          id: 'favorite_color',
          name: 'Favorite Color',
          type: 'field'
        }
      ],
      rules: [],
      result_name: ''
    };

    const uiConfig = split_by_contact_field.toUIConfig!(formData);

    expect(uiConfig.operand).to.exist;
    expect(uiConfig.operand.id).to.equal('favorite_color');
    expect(uiConfig.operand.name).to.equal('Favorite Color');
    expect(uiConfig.operand.type).to.equal('field');
  });

  it('should transform from form data to flow definition for URN scheme', () => {
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [],
        categories: [],
        default_category_uuid: '',
        operand: '@input.text'
      },
      exits: []
    };

    const formData = {
      uuid: 'test-node-uuid',
      field: [{ value: 'facebook', name: 'Facebook', type: 'scheme' }],
      rules: [
        {
          operator: { value: 'has_only_phrase', name: 'has only the phrase' },
          value1: '123456789',
          value2: '',
          category: 'Valid Facebook ID'
        }
      ],
      result_name: 'facebook_id'
    };

    const updatedNode = split_by_contact_field.fromFormData!(
      formData,
      originalNode
    );

    // The operand should be splitting on the Facebook URN path (the ID)
    expect(updatedNode.router!.operand).to.equal(
      '@(default(urn_parts(urns.facebook).path, ""))'
    );
    expect(updatedNode.router!.result_name).to.equal('facebook_id');
    expect(updatedNode.router!.cases.length).to.equal(1);
    expect(updatedNode.router!.cases[0].type).to.equal('has_only_phrase');
    expect(updatedNode.router!.cases[0].arguments).to.deep.equal(['123456789']);
  });

  it('should transform from flow definition to form data for URN scheme', () => {
    const node: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_only_phrase',
            arguments: ['987654321'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Valid WhatsApp', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@(default(urn_parts(urns.whatsapp).path, ""))',
        result_name: 'whatsapp_number'
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    const nodeUI = {
      type: 'split_by_contact_field',
      position: { left: 0, top: 0 },
      config: {
        operand: {
          id: 'whatsapp',
          name: 'WhatsApp',
          type: 'scheme'
        }
      }
    };

    const formData = split_by_contact_field.toFormData!(node, nodeUI);

    expect(formData.uuid).to.equal('test-node-uuid');
    expect(formData.field).to.have.lengthOf(1);
    expect(formData.field[0].id).to.equal('whatsapp');
    expect(formData.field[0].name).to.equal('WhatsApp');
    expect(formData.field[0].type).to.equal('scheme');
    expect(formData.result_name).to.equal('whatsapp_number');
  });

  it('should generate UI config from form data for URN scheme', () => {
    const formData = {
      field: [{ value: 'facebook', name: 'Facebook', type: 'scheme' }],
      rules: [],
      result_name: ''
    };

    const uiConfig = split_by_contact_field.toUIConfig!(formData);

    expect(uiConfig.operand).to.exist;
    expect(uiConfig.operand.id).to.equal('facebook');
    expect(uiConfig.operand.name).to.equal('Facebook');
    expect(uiConfig.operand.type).to.equal('scheme');
  });

  it('should handle round-trip for custom field without re-selecting', () => {
    // Reproduces the bug: toUIConfig saves { id, name, type } without 'key',
    // then toFormData loads it, and fromFormData must still produce a valid operand.
    const originalNode: Node = {
      uuid: 'test-node-uuid',
      actions: [],
      router: {
        type: 'switch',
        cases: [
          {
            uuid: 'case-1',
            type: 'has_text',
            arguments: ['red'],
            category_uuid: 'cat-1'
          }
        ],
        categories: [
          { uuid: 'cat-1', name: 'Red', exit_uuid: 'exit-1' },
          { uuid: 'cat-other', name: 'Other', exit_uuid: 'exit-other' }
        ],
        default_category_uuid: 'cat-other',
        operand: '@fields.favorite_color',
        result_name: ''
      },
      exits: [
        { uuid: 'exit-1', destination_uuid: null },
        { uuid: 'exit-other', destination_uuid: null }
      ]
    };

    // nodeUI as saved by toUIConfig - note: NO 'key' property, only 'id'
    const nodeUI = {
      type: 'split_by_contact_field',
      position: { left: 0, top: 0 },
      config: {
        operand: {
          id: 'favorite_color',
          name: 'Favorite Color',
          type: 'field'
        }
      }
    };

    // Step 1: toFormData (opening the editor)
    const formData = split_by_contact_field.toFormData!(originalNode, nodeUI);

    // The field should have 'key' normalized from 'id'
    expect(formData.field[0].key).to.equal('favorite_color');

    // Step 2: fromFormData (saving without re-selecting the field)
    const updatedNode = split_by_contact_field.fromFormData!(
      formData,
      originalNode
    );

    // The operand must NOT be @fields.undefined
    expect(updatedNode.router!.operand).to.equal('@fields.favorite_color');
  });
});
