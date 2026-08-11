import { expect } from '@open-wc/testing';
import { set_contact_channel } from '../../src/flow/actions/set_contact_channel';
import { SetContactChannel } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the set_contact_channel action configuration.
 */
describe('set_contact_channel action config', () => {
  const helper = new ActionTest(set_contact_channel, 'set_contact_channel');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(set_contact_channel.name).to.equal('Update Channel');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'set_contact_channel',
        channel: { uuid: 'channel-1', name: 'WhatsApp Channel' }
      } as SetContactChannel,
      'whatsapp-channel'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'set_contact_channel',
        channel: { uuid: 'channel-2', name: 'Twilio SMS' }
      } as SetContactChannel,
      'sms-channel'
    );
  });

  describe('metadata stripping', () => {
    it('should strip superfluous API metadata from channel', () => {
      const formData = {
        uuid: 'test-uuid',
        channel: [
          {
            uuid: 'channel-1',
            name: 'WhatsApp Channel',
            address: '+250788123456',
            country: 'RW',
            schemes: ['whatsapp'],
            roles: ['send', 'receive'],
            created_on: '2024-01-01T00:00:00.000Z'
          }
        ]
      };

      const action = set_contact_channel.fromFormData(
        formData
      ) as SetContactChannel;

      expect(action.channel).to.deep.equal({
        uuid: 'channel-1',
        name: 'WhatsApp Channel'
      });
    });

    it('should handle channel selected via value key', () => {
      const formData = {
        uuid: 'test-uuid',
        channel: [
          {
            value: 'channel-1',
            name: 'WhatsApp Channel'
          }
        ]
      };

      const action = set_contact_channel.fromFormData(
        formData
      ) as SetContactChannel;

      expect(action.channel).to.deep.equal({
        uuid: 'channel-1',
        name: 'WhatsApp Channel'
      });
    });
  });
});
