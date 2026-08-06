import { expect } from '@open-wc/testing';
import { wait_for_audio } from '../../src/flow/nodes/wait_for_audio';
import { Node } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the wait_for_audio node configuration.
 */
describe('wait_for_audio node config', () => {
  const helper = new NodeTest(wait_for_audio, 'wait_for_audio');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(wait_for_audio.name).to.equal('Make Recording');
    });

    it('has correct type', () => {
      expect(wait_for_audio.type).to.equal('wait_for_audio');
    });

    it('is voice-only', () => {
      expect(wait_for_audio.flowTypes).to.deep.equal(['voice']);
    });

    it('has form with result_name field', () => {
      expect(wait_for_audio.form).to.exist;
      expect(wait_for_audio.form!.result_name).to.exist;
    });

    it('has layout', () => {
      expect(wait_for_audio.layout).to.deep.equal(['result_name']);
    });
  });

  describe('node scenarios', () => {
    it('renders basic audio wait', async () => {
      await helper.testNode(
        {
          uuid: 'test-audio-node-1',
          actions: [],
          router: {
            type: 'switch',
            operand: '@input',
            wait: {
              type: 'msg',
              hint: { type: 'audio' }
            },
            result_name: 'recording',
            default_category_uuid: 'all-cat-1',
            cases: [],
            categories: [
              {
                uuid: 'all-cat-1',
                name: 'All Responses',
                exit_uuid: 'all-exit-1'
              }
            ]
          },
          exits: [{ uuid: 'all-exit-1', destination_uuid: null }]
        } as Node,
        { type: 'wait_for_audio' },
        'basic-audio-wait'
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
          result_name: 'my_recording',
          categories: []
        },
        exits: []
      };

      const formData = wait_for_audio.toFormData!(node);
      expect(formData.uuid).to.equal('test-node');
      expect(formData.result_name).to.equal('my_recording');
    });

    it('handles missing result_name', () => {
      const node: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: []
        },
        exits: []
      };

      const formData = wait_for_audio.toFormData!(node);
      expect(formData.result_name).to.equal('');
    });

    it('creates node with All Responses category', () => {
      const formData = {
        uuid: 'test-node',
        result_name: 'recording'
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: {
          type: 'switch',
          categories: []
        }
      };

      const result = wait_for_audio.fromFormData!(formData, originalNode);

      expect(result.router?.categories).to.have.length(1);
      expect(result.router?.categories[0].name).to.equal('All Responses');
      expect(result.router?.wait?.type).to.equal('msg');
      expect(result.router?.wait?.hint?.type).to.equal('audio');
      expect(result.router?.result_name).to.equal('recording');
      expect(result.exits).to.have.length(1);
    });

    it('preserves existing All Responses category UUID', () => {
      const formData = {
        uuid: 'test-node',
        result_name: 'recording'
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: [
            {
              uuid: 'existing-cat-uuid',
              name: 'All Responses',
              exit_uuid: 'existing-exit-uuid'
            }
          ]
        },
        exits: [
          {
            uuid: 'existing-exit-uuid',
            destination_uuid: 'some-destination'
          }
        ]
      };

      const result = wait_for_audio.fromFormData!(formData, originalNode);

      expect(result.router?.categories[0].uuid).to.equal('existing-cat-uuid');
      expect(result.router?.categories[0].exit_uuid).to.equal(
        'existing-exit-uuid'
      );
      expect(result.exits[0].uuid).to.equal('existing-exit-uuid');
      expect(result.exits[0].destination_uuid).to.equal('some-destination');
    });

    it('omits result_name when empty', () => {
      const formData = {
        uuid: 'test-node',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_audio.fromFormData!(formData, originalNode);
      expect(result.router?.result_name).to.be.undefined;
    });
  });
});
