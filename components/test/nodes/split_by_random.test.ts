import { expect } from '@open-wc/testing';
import { split_by_random } from '../../src/flow/nodes/split_by_random';
import { Node } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the split_by_random node configuration.
 */
describe('split_by_random node config', () => {
  const helper = new NodeTest(split_by_random, 'split_by_random');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(split_by_random.name).to.equal('Random Split');
    });

    it('has correct type', () => {
      expect(split_by_random.type).to.equal('split_by_random');
    });

    it('has correct group', () => {
      expect(split_by_random.group).to.exist;
    });

    it('has router configuration', () => {
      expect(split_by_random.router).to.exist;
      expect(split_by_random.router.type).to.equal('random');
    });

    it('has a result name field', () => {
      expect(split_by_random.form.result_name).to.exist;
      expect(split_by_random.layout).to.have.lengthOf(2);
    });
  });

  describe('form data transformation', () => {
    const node = (result_name?: string): Node =>
      ({
        uuid: 'test-node-uuid',
        actions: [],
        router: {
          type: 'random',
          categories: [
            { uuid: 'cat-1', name: 'Bucket A', exit_uuid: 'exit-1' },
            { uuid: 'cat-2', name: 'Bucket B', exit_uuid: 'exit-2' }
          ],
          ...(result_name ? { result_name } : {})
        },
        exits: [
          { uuid: 'exit-1', destination_uuid: null },
          { uuid: 'exit-2', destination_uuid: null }
        ]
      }) as Node;

    it('reads the result name from the router', () => {
      const formData = split_by_random.toFormData!(node('My Bucket'));

      expect(formData.uuid).to.equal('test-node-uuid');
      expect(formData.categories).to.have.lengthOf(2);
      expect(formData.result_name).to.equal('My Bucket');
    });

    it('defaults the result name to empty when not set', () => {
      expect(split_by_random.toFormData!(node()).result_name).to.equal('');
    });

    it('writes the result name onto the router', () => {
      const resultNode = split_by_random.fromFormData!(
        {
          uuid: 'test-node-uuid',
          categories: [{ name: 'Bucket A' }, { name: 'Bucket B' }],
          result_name: '  My Bucket  '
        },
        { uuid: 'test-node-uuid', actions: [], exits: [] } as Node
      );

      expect(resultNode.router!.type).to.equal('random');
      expect(resultNode.router!.categories).to.have.lengthOf(2);
      expect(resultNode.router!.result_name).to.equal('My Bucket');
    });

    it('omits the result name when empty', () => {
      const resultNode = split_by_random.fromFormData!(
        {
          uuid: 'test-node-uuid',
          categories: [{ name: 'Bucket A' }, { name: 'Bucket B' }],
          result_name: '  '
        },
        { uuid: 'test-node-uuid', actions: [], exits: [] } as Node
      );

      expect(resultNode.router).to.not.have.property('result_name');
    });

    it('preserves an existing result name through a round trip', () => {
      const original = node('My Bucket');
      const resultNode = split_by_random.fromFormData!(
        split_by_random.toFormData!(original),
        original
      );

      expect(resultNode.router!.result_name).to.equal('My Bucket');
    });
  });

  describe('node scenarios', () => {
    it('renders two bucket split', async () => {
      await helper.testNode(
        {
          uuid: 'test-random-node-1',
          actions: [],
          router: {
            type: 'random',
            categories: [
              {
                uuid: 'random-cat-1',
                name: 'Bucket A',
                exit_uuid: 'random-exit-1'
              },
              {
                uuid: 'random-cat-2',
                name: 'Bucket B',
                exit_uuid: 'random-exit-2'
              }
            ]
          },
          exits: [
            { uuid: 'random-exit-1', destination_uuid: null },
            { uuid: 'random-exit-2', destination_uuid: null }
          ]
        } as Node,
        { type: 'split_by_random' },
        'two-bucket-split'
      );
    });

    it('renders three way split', async () => {
      await helper.testNode(
        {
          uuid: 'test-random-node-2',
          actions: [],
          router: {
            type: 'random',
            categories: [
              {
                uuid: 'random-cat-1',
                name: 'Group A',
                exit_uuid: 'random-exit-1'
              },
              {
                uuid: 'random-cat-2',
                name: 'Group B',
                exit_uuid: 'random-exit-2'
              },
              {
                uuid: 'random-cat-3',
                name: 'Group C',
                exit_uuid: 'random-exit-3'
              }
            ]
          },
          exits: [
            { uuid: 'random-exit-1', destination_uuid: null },
            { uuid: 'random-exit-2', destination_uuid: null },
            { uuid: 'random-exit-3', destination_uuid: null }
          ]
        } as Node,
        { type: 'split_by_random' },
        'three-way-split'
      );
    });

    it('renders ab test multiple variants', async () => {
      await helper.testNode(
        {
          uuid: 'test-random-node-3',
          actions: [],
          router: {
            type: 'random',
            categories: [
              {
                uuid: 'random-cat-1',
                name: 'Treatment',
                exit_uuid: 'random-exit-1'
              },
              {
                uuid: 'random-cat-2',
                name: 'Control',
                exit_uuid: 'random-exit-2'
              },
              {
                uuid: 'random-cat-3',
                name: 'Variant A',
                exit_uuid: 'random-exit-3'
              },
              {
                uuid: 'random-cat-4',
                name: 'Variant B',
                exit_uuid: 'random-exit-4'
              },
              {
                uuid: 'random-cat-5',
                name: 'Holdout',
                exit_uuid: 'random-exit-5'
              }
            ]
          },
          exits: [
            { uuid: 'random-exit-1', destination_uuid: null },
            { uuid: 'random-exit-2', destination_uuid: null },
            { uuid: 'random-exit-3', destination_uuid: null },
            { uuid: 'random-exit-4', destination_uuid: null },
            { uuid: 'random-exit-5', destination_uuid: null }
          ]
        } as Node,
        { type: 'split_by_random' },
        'ab-test-multiple-variants'
      );
    });

    it('renders sampling split', async () => {
      await helper.testNode(
        {
          uuid: 'test-random-node-4',
          actions: [],
          router: {
            type: 'random',
            categories: [
              {
                uuid: 'random-cat-1',
                name: 'Sample Group',
                exit_uuid: 'random-exit-1'
              },
              {
                uuid: 'random-cat-2',
                name: 'Remaining Population',
                exit_uuid: 'random-exit-2'
              }
            ]
          },
          exits: [
            { uuid: 'random-exit-1', destination_uuid: null },
            { uuid: 'random-exit-2', destination_uuid: null }
          ]
        } as Node,
        { type: 'split_by_random' },
        'sampling-split'
      );
    });
  });
});
