import { expect } from '@open-wc/testing';
import { split_by_ticket } from '../../src/flow/nodes/split_by_ticket';
import { Node, OpenTicket } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the split_by_ticket node configuration.
 */
describe('split_by_ticket node config', () => {
  const helper = new NodeTest(split_by_ticket, 'split_by_ticket');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct type and name', () => {
      expect(split_by_ticket.type).to.equal('split_by_ticket');
      expect(split_by_ticket.name).to.equal('Open Ticket');
    });

    it('enables expression completion on the note field', () => {
      expect((split_by_ticket.form!.note as any).evaluated).to.equal(true);
    });
  });

  describe('round-trip transformation', () => {
    it('should transform from flow definition to form data', () => {
      const node: Node = {
        uuid: 'test-node',
        actions: [
          {
            type: 'open_ticket',
            uuid: 'action-1',
            topic: { uuid: 'topic-1', name: 'General' },
            assignee: { uuid: 'user-1', name: 'Alice' },
            note: 'Test note'
          } as OpenTicket
        ],
        exits: []
      };

      const formData = split_by_ticket.toFormData!(node);

      expect(formData.uuid).to.equal('test-node');
      expect(formData.topic).to.have.lengthOf(1);
      expect(formData.topic[0]).to.deep.equal({
        uuid: 'topic-1',
        name: 'General'
      });
      expect(formData.assignee).to.have.lengthOf(1);
      expect(formData.assignee[0]).to.deep.equal({
        uuid: 'user-1',
        name: 'Alice'
      });
      expect(formData.note).to.equal('Test note');
    });

    it('should transform from form data to flow definition', () => {
      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node',
        topic: [{ uuid: 'topic-1', name: 'General' }],
        assignee: [{ uuid: 'user-1', name: 'Alice' }],
        note: 'Test note'
      };

      const resultNode = split_by_ticket.fromFormData!(formData, originalNode);

      expect(resultNode.uuid).to.equal('test-node');
      expect(resultNode.actions).to.have.lengthOf(1);
      expect(resultNode.actions![0].type).to.equal('open_ticket');
      expect((resultNode.actions![0] as any).topic).to.deep.equal({
        uuid: 'topic-1',
        name: 'General'
      });
      expect((resultNode.actions![0] as any).assignee).to.deep.equal({
        uuid: 'user-1',
        name: 'Alice'
      });
    });

    it('should strip superfluous API metadata from topic and assignee', () => {
      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node',
        topic: [
          {
            uuid: 'topic-1',
            name: 'General',
            created_on: '2024-01-01T00:00:00.000Z',
            modified_on: '2024-06-15T12:00:00.000Z'
          }
        ],
        assignee: [
          {
            uuid: 'user-1',
            name: 'Alice Johnson',
            email: 'alice@example.com',
            first_name: 'Alice',
            last_name: 'Johnson',
            role: 'agent',
            created_on: '2024-01-01T00:00:00.000Z'
          }
        ],
        note: ''
      };

      const resultNode = split_by_ticket.fromFormData!(formData, originalNode);

      const action = resultNode.actions![0] as any;
      expect(action.topic).to.deep.equal({
        uuid: 'topic-1',
        name: 'General'
      });
      expect(action.assignee).to.deep.equal({
        uuid: 'user-1',
        name: 'Alice Johnson'
      });
    });

    it('should handle assignee with only first_name/last_name (no name)', () => {
      const originalNode: Node = {
        uuid: 'test-node',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node',
        topic: [{ uuid: 'topic-1', name: 'General' }],
        assignee: [
          {
            uuid: 'user-1',
            first_name: 'Bob',
            last_name: 'Smith',
            email: 'bob@example.com',
            role: 'agent'
          }
        ],
        note: ''
      };

      const resultNode = split_by_ticket.fromFormData!(formData, originalNode);

      const action = resultNode.actions![0] as any;
      expect(action.assignee).to.deep.equal({
        uuid: 'user-1',
        name: 'Bob Smith'
      });
    });
  });
});
