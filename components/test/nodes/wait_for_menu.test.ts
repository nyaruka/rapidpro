import { expect } from '@open-wc/testing';
import { wait_for_menu } from '../../src/flow/nodes/wait_for_menu';
import { Node } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the wait_for_menu node configuration.
 */
describe('wait_for_menu node config', () => {
  const helper = new NodeTest(wait_for_menu, 'wait_for_menu');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(wait_for_menu.name).to.equal('Wait for Menu');
    });

    it('has correct type', () => {
      expect(wait_for_menu.type).to.equal('wait_for_menu');
    });

    it('is voice-only', () => {
      expect(wait_for_menu.flowTypes).to.deep.equal(['voice']);
    });

    it('has form with 10 digit fields plus result_name', () => {
      expect(wait_for_menu.form).to.exist;
      for (const d of ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']) {
        expect(wait_for_menu.form![`digit_${d}`]).to.exist;
      }
      expect(wait_for_menu.form!.result_name).to.exist;
    });
  });

  describe('node scenarios', () => {
    it('renders menu with filled digits', async () => {
      await helper.testNode(
        {
          uuid: 'test-menu-node-1',
          actions: [],
          router: {
            type: 'switch',
            operand: '@input.text',
            wait: {
              type: 'msg',
              hint: { type: 'digits', count: 1 }
            },
            result_name: 'menu_choice',
            default_category_uuid: 'other-cat',
            cases: [
              {
                uuid: 'case-1',
                type: 'has_number_eq',
                arguments: ['1'],
                category_uuid: 'sales-cat'
              },
              {
                uuid: 'case-2',
                type: 'has_number_eq',
                arguments: ['2'],
                category_uuid: 'support-cat'
              },
              {
                uuid: 'case-0',
                type: 'has_number_eq',
                arguments: ['0'],
                category_uuid: 'operator-cat'
              }
            ],
            categories: [
              {
                uuid: 'sales-cat',
                name: 'Sales',
                exit_uuid: 'sales-exit'
              },
              {
                uuid: 'support-cat',
                name: 'Support',
                exit_uuid: 'support-exit'
              },
              {
                uuid: 'operator-cat',
                name: 'Operator',
                exit_uuid: 'operator-exit'
              },
              {
                uuid: 'other-cat',
                name: 'Other',
                exit_uuid: 'other-exit'
              }
            ]
          },
          exits: [
            { uuid: 'sales-exit', destination_uuid: null },
            { uuid: 'support-exit', destination_uuid: null },
            { uuid: 'operator-exit', destination_uuid: null },
            { uuid: 'other-exit', destination_uuid: null }
          ]
        } as Node,
        { type: 'wait_for_menu' },
        'menu-with-digits'
      );
    });
  });

  describe('data transformation', () => {
    it('converts node to form data', () => {
      const node: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          result_name: 'menu',
          categories: [
            {
              uuid: 'sales-cat',
              name: 'Sales',
              exit_uuid: 'sales-exit'
            },
            {
              uuid: 'support-cat',
              name: 'Support',
              exit_uuid: 'support-exit'
            },
            {
              uuid: 'other-cat',
              name: 'Other',
              exit_uuid: 'other-exit'
            }
          ],
          cases: [
            {
              uuid: 'case-1',
              type: 'has_number_eq',
              arguments: ['1'],
              category_uuid: 'sales-cat'
            },
            {
              uuid: 'case-2',
              type: 'has_number_eq',
              arguments: ['2'],
              category_uuid: 'support-cat'
            }
          ]
        },
        exits: [
          { uuid: 'sales-exit', destination_uuid: null },
          { uuid: 'support-exit', destination_uuid: null },
          { uuid: 'other-exit', destination_uuid: null }
        ]
      };

      const formData = wait_for_menu.toFormData!(node);

      expect(formData.uuid).to.equal('test-node');
      expect(formData.digit_1).to.equal('Sales');
      expect(formData.digit_2).to.equal('Support');
      expect(formData.digit_3).to.equal('');
      expect(formData.digit_0).to.equal('');
      expect(formData.result_name).to.equal('menu');
    });

    it('handles empty menu', () => {
      const node: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: []
        },
        exits: []
      };

      const formData = wait_for_menu.toFormData!(node);

      for (const d of ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']) {
        expect(formData[`digit_${d}`]).to.equal('');
      }
    });

    it('creates node from form data with filled digits', () => {
      const formData = {
        uuid: 'test-node',
        digit_1: 'Sales',
        digit_2: 'Support',
        digit_3: '',
        digit_4: '',
        digit_5: '',
        digit_6: '',
        digit_7: '',
        digit_8: '',
        digit_9: '',
        digit_0: 'Operator',
        result_name: 'menu_choice'
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_menu.fromFormData!(formData, originalNode);

      // Should have 4 categories: Sales, Support, Operator, Other
      expect(result.router?.categories).to.have.length(4);
      const names = result.router!.categories.map((c) => c.name);
      expect(names).to.deep.equal(['Sales', 'Support', 'Operator', 'Other']);

      // Should have 3 cases
      expect(result.router?.cases).to.have.length(3);
      expect(result.router!.cases[0].arguments).to.deep.equal(['1']);
      expect(result.router!.cases[1].arguments).to.deep.equal(['2']);
      expect(result.router!.cases[2].arguments).to.deep.equal(['0']);

      // Check wait config
      expect(result.router?.wait?.type).to.equal('msg');
      expect(result.router?.wait?.hint?.type).to.equal('digits');
      expect(result.router?.wait?.hint?.count).to.equal(1);

      // Check result name
      expect(result.router?.result_name).to.equal('menu_choice');

      // 4 exits
      expect(result.exits).to.have.length(4);
    });

    it('merges duplicate category names', () => {
      const formData = {
        uuid: 'test-node',
        digit_1: 'Sales',
        digit_2: 'Sales', // same category name
        digit_3: '',
        digit_4: '',
        digit_5: '',
        digit_6: '',
        digit_7: '',
        digit_8: '',
        digit_9: '',
        digit_0: '',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_menu.fromFormData!(formData, originalNode);

      // Should have 2 categories: Sales and Other (not duplicate Sales)
      expect(result.router?.categories).to.have.length(2);
      expect(result.router!.categories[0].name).to.equal('Sales');
      expect(result.router!.categories[1].name).to.equal('Other');

      // Both cases should reference same category
      expect(result.router?.cases).to.have.length(2);
      expect(result.router!.cases[0].category_uuid).to.equal(
        result.router!.cases[1].category_uuid
      );

      // Should have 2 exits (not 3)
      expect(result.exits).to.have.length(2);
    });

    it('preserves existing category UUIDs', () => {
      const formData = {
        uuid: 'test-node',
        digit_1: 'Sales',
        digit_2: 'Support',
        digit_3: '',
        digit_4: '',
        digit_5: '',
        digit_6: '',
        digit_7: '',
        digit_8: '',
        digit_9: '',
        digit_0: '',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: [
            {
              uuid: 'orig-sales',
              name: 'Sales',
              exit_uuid: 'orig-sales-exit'
            },
            {
              uuid: 'orig-support',
              name: 'Support',
              exit_uuid: 'orig-support-exit'
            },
            {
              uuid: 'orig-other',
              name: 'Other',
              exit_uuid: 'orig-other-exit'
            }
          ],
          cases: [
            {
              uuid: 'orig-case-1',
              type: 'has_number_eq',
              arguments: ['1'],
              category_uuid: 'orig-sales'
            },
            {
              uuid: 'orig-case-2',
              type: 'has_number_eq',
              arguments: ['2'],
              category_uuid: 'orig-support'
            }
          ]
        },
        exits: [
          { uuid: 'orig-sales-exit', destination_uuid: 'dest-1' },
          { uuid: 'orig-support-exit', destination_uuid: 'dest-2' },
          { uuid: 'orig-other-exit', destination_uuid: null }
        ]
      };

      const result = wait_for_menu.fromFormData!(formData, originalNode);

      // Category UUIDs preserved
      const sales = result.router!.categories.find((c) => c.name === 'Sales');
      expect(sales?.uuid).to.equal('orig-sales');
      expect(sales?.exit_uuid).to.equal('orig-sales-exit');

      const other = result.router!.categories.find((c) => c.name === 'Other');
      expect(other?.uuid).to.equal('orig-other');

      // Case UUIDs preserved
      const case1 = result.router!.cases.find(
        (c: any) => c.arguments[0] === '1'
      );
      expect(case1?.uuid).to.equal('orig-case-1');

      // Exit destinations preserved
      const salesExit = result.exits.find((e) => e.uuid === 'orig-sales-exit');
      expect(salesExit?.destination_uuid).to.equal('dest-1');
    });

    it('handles all empty digits', () => {
      const formData = {
        uuid: 'test-node',
        digit_1: '',
        digit_2: '',
        digit_3: '',
        digit_4: '',
        digit_5: '',
        digit_6: '',
        digit_7: '',
        digit_8: '',
        digit_9: '',
        digit_0: '',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_menu.fromFormData!(formData, originalNode);

      // Should still have Other category
      expect(result.router?.categories).to.have.length(1);
      expect(result.router!.categories[0].name).to.equal('Other');
      expect(result.router?.cases).to.have.length(0);
      expect(result.exits).to.have.length(1);
    });
  });
});
