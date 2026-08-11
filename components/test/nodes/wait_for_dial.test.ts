import { expect } from '@open-wc/testing';
import { wait_for_dial } from '../../src/flow/nodes/wait_for_dial';
import { Node } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the wait_for_dial node configuration.
 */
describe('wait_for_dial node config', () => {
  const helper = new NodeTest(wait_for_dial, 'wait_for_dial');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(wait_for_dial.name).to.equal('Redirect Call');
    });

    it('has correct type', () => {
      expect(wait_for_dial.type).to.equal('wait_for_dial');
    });

    it('is voice-only', () => {
      expect(wait_for_dial.flowTypes).to.deep.equal(['voice']);
    });

    it('has form with phone and limit fields', () => {
      expect(wait_for_dial.form).to.exist;
      expect(wait_for_dial.form!.phone).to.exist;
      expect(wait_for_dial.form!.dial_limit_seconds).to.exist;
      expect(wait_for_dial.form!.call_limit_seconds).to.exist;
      expect(wait_for_dial.form!.result_name).to.exist;
    });

    it('has fixed router rules', () => {
      expect(wait_for_dial.router).to.exist;
      expect(wait_for_dial.router!.type).to.equal('switch');
      expect(wait_for_dial.router!.defaultCategory).to.equal('Failed');
      expect(wait_for_dial.router!.rules).to.have.length(3);
    });
  });

  describe('node scenarios', () => {
    it('renders basic dial', async () => {
      await helper.testNode(
        {
          uuid: 'test-dial-node-1',
          actions: [],
          router: {
            type: 'switch',
            operand: '@(default(resume.dial.status, ""))',
            wait: {
              type: 'dial',
              phone: '+12065551234'
            },
            result_name: 'dial_result',
            default_category_uuid: 'failed-cat',
            cases: [
              {
                uuid: 'case-answered',
                type: 'has_only_text',
                arguments: ['answered'],
                category_uuid: 'answered-cat'
              },
              {
                uuid: 'case-no-answer',
                type: 'has_only_text',
                arguments: ['no_answer'],
                category_uuid: 'no-answer-cat'
              },
              {
                uuid: 'case-busy',
                type: 'has_only_text',
                arguments: ['busy'],
                category_uuid: 'busy-cat'
              }
            ],
            categories: [
              {
                uuid: 'answered-cat',
                name: 'Answered',
                exit_uuid: 'answered-exit'
              },
              {
                uuid: 'no-answer-cat',
                name: 'No Answer',
                exit_uuid: 'no-answer-exit'
              },
              {
                uuid: 'busy-cat',
                name: 'Busy',
                exit_uuid: 'busy-exit'
              },
              {
                uuid: 'failed-cat',
                name: 'Failed',
                exit_uuid: 'failed-exit'
              }
            ]
          },
          exits: [
            { uuid: 'answered-exit', destination_uuid: null },
            { uuid: 'no-answer-exit', destination_uuid: null },
            { uuid: 'busy-exit', destination_uuid: null },
            { uuid: 'failed-exit', destination_uuid: null }
          ]
        } as Node,
        { type: 'wait_for_dial' },
        'basic-dial'
      );
    });

    it('renders dial with limits', async () => {
      await helper.testNode(
        {
          uuid: 'test-dial-node-2',
          actions: [],
          router: {
            type: 'switch',
            operand: '@(default(resume.dial.status, ""))',
            wait: {
              type: 'dial',
              phone: '@contact.phone',
              dial_limit_seconds: 30,
              call_limit_seconds: 3600
            },
            default_category_uuid: 'failed-cat',
            cases: [
              {
                uuid: 'case-answered',
                type: 'has_only_text',
                arguments: ['answered'],
                category_uuid: 'answered-cat'
              },
              {
                uuid: 'case-no-answer',
                type: 'has_only_text',
                arguments: ['no_answer'],
                category_uuid: 'no-answer-cat'
              },
              {
                uuid: 'case-busy',
                type: 'has_only_text',
                arguments: ['busy'],
                category_uuid: 'busy-cat'
              }
            ],
            categories: [
              {
                uuid: 'answered-cat',
                name: 'Answered',
                exit_uuid: 'answered-exit'
              },
              {
                uuid: 'no-answer-cat',
                name: 'No Answer',
                exit_uuid: 'no-answer-exit'
              },
              {
                uuid: 'busy-cat',
                name: 'Busy',
                exit_uuid: 'busy-exit'
              },
              {
                uuid: 'failed-cat',
                name: 'Failed',
                exit_uuid: 'failed-exit'
              }
            ]
          },
          exits: [
            { uuid: 'answered-exit', destination_uuid: null },
            { uuid: 'no-answer-exit', destination_uuid: null },
            { uuid: 'busy-exit', destination_uuid: null },
            { uuid: 'failed-exit', destination_uuid: null }
          ]
        } as Node,
        { type: 'wait_for_dial' },
        'dial-with-limits'
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
          result_name: 'dial_result',
          wait: {
            type: 'dial',
            phone: '+12065551234',
            dial_limit_seconds: 60,
            call_limit_seconds: 7200
          },
          categories: []
        },
        exits: []
      };

      const formData = wait_for_dial.toFormData!(node);
      expect(formData.uuid).to.equal('test-node');
      expect(formData.phone).to.equal('+12065551234');
      expect(formData.dial_limit_seconds).to.equal('60');
      expect(formData.call_limit_seconds).to.equal('7200');
      expect(formData.result_name).to.equal('dial_result');
    });

    it('handles missing wait config', () => {
      const node: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: []
        },
        exits: []
      };

      const formData = wait_for_dial.toFormData!(node);
      expect(formData.phone).to.equal('');
      expect(formData.dial_limit_seconds).to.equal('');
      expect(formData.call_limit_seconds).to.equal('');
    });

    it('creates node with fixed dial categories', () => {
      const formData = {
        uuid: 'test-node',
        phone: '+12065551234',
        dial_limit_seconds: '60',
        call_limit_seconds: '7200',
        result_name: 'dial_result'
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_dial.fromFormData!(formData, originalNode);

      // Should have 4 fixed categories
      expect(result.router?.categories).to.have.length(4);
      const names = result.router!.categories.map((c) => c.name);
      expect(names).to.deep.equal(['Answered', 'No Answer', 'Busy', 'Failed']);

      // Should have 3 cases (Failed is default, no case needed)
      expect(result.router?.cases).to.have.length(3);

      // Check wait config
      expect(result.router?.wait?.type).to.equal('dial');
      expect(result.router?.wait?.phone).to.equal('+12065551234');
      expect(result.router?.wait?.dial_limit_seconds).to.equal(60);
      expect(result.router?.wait?.call_limit_seconds).to.equal(7200);

      // Check operand
      expect(result.router?.operand).to.equal(
        '@(default(resume.dial.status, ""))'
      );

      // Check result name
      expect(result.router?.result_name).to.equal('dial_result');

      // Should have 4 exits
      expect(result.exits).to.have.length(4);
    });

    it('omits limits when empty', () => {
      const formData = {
        uuid: 'test-node',
        phone: '+12065551234',
        dial_limit_seconds: '',
        call_limit_seconds: '',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: [],
        router: { type: 'switch', categories: [] }
      };

      const result = wait_for_dial.fromFormData!(formData, originalNode);

      expect(result.router?.wait?.dial_limit_seconds).to.be.undefined;
      expect(result.router?.wait?.call_limit_seconds).to.be.undefined;
      expect(result.router?.result_name).to.be.undefined;
    });

    it('preserves existing category UUIDs', () => {
      const formData = {
        uuid: 'test-node',
        phone: '+12065551234',
        dial_limit_seconds: '',
        call_limit_seconds: '',
        result_name: ''
      };

      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        router: {
          type: 'switch',
          categories: [
            {
              uuid: 'orig-answered',
              name: 'Answered',
              exit_uuid: 'orig-answered-exit'
            },
            {
              uuid: 'orig-no-answer',
              name: 'No Answer',
              exit_uuid: 'orig-no-answer-exit'
            },
            {
              uuid: 'orig-busy',
              name: 'Busy',
              exit_uuid: 'orig-busy-exit'
            },
            {
              uuid: 'orig-failed',
              name: 'Failed',
              exit_uuid: 'orig-failed-exit'
            }
          ],
          cases: [
            {
              uuid: 'orig-case-answered',
              type: 'has_only_text',
              arguments: ['answered'],
              category_uuid: 'orig-answered'
            },
            {
              uuid: 'orig-case-no-answer',
              type: 'has_only_text',
              arguments: ['no_answer'],
              category_uuid: 'orig-no-answer'
            },
            {
              uuid: 'orig-case-busy',
              type: 'has_only_text',
              arguments: ['busy'],
              category_uuid: 'orig-busy'
            }
          ]
        },
        exits: [
          { uuid: 'orig-answered-exit', destination_uuid: 'dest-1' },
          { uuid: 'orig-no-answer-exit', destination_uuid: 'dest-2' },
          { uuid: 'orig-busy-exit', destination_uuid: null },
          { uuid: 'orig-failed-exit', destination_uuid: null }
        ]
      };

      const result = wait_for_dial.fromFormData!(formData, originalNode);

      // Category UUIDs should be preserved
      const answered = result.router!.categories.find(
        (c) => c.name === 'Answered'
      );
      expect(answered?.uuid).to.equal('orig-answered');
      expect(answered?.exit_uuid).to.equal('orig-answered-exit');

      // Exit destinations should be preserved
      const answeredExit = result.exits.find(
        (e) => e.uuid === 'orig-answered-exit'
      );
      expect(answeredExit?.destination_uuid).to.equal('dest-1');

      // Case UUIDs should be preserved
      const answeredCase = result.router!.cases.find(
        (c: any) => c.arguments[0] === 'answered'
      );
      expect(answeredCase?.uuid).to.equal('orig-case-answered');
    });
  });
});
