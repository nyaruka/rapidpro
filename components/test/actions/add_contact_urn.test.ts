import { expect } from '@open-wc/testing';
import { add_contact_urn } from '../../src/flow/actions/add_contact_urn';
import { AddContactUrn } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the add_contact_urn action configuration.
 */
describe('add_contact_urn action config', () => {
  const helper = new ActionTest(add_contact_urn, 'add_contact_urn');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(add_contact_urn.name).to.equal('Add URN');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'add_contact_urn',
        scheme: 'tel',
        path: '+12065551212'
      } as AddContactUrn,
      'phone-number'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'add_contact_urn',
        scheme: 'whatsapp',
        path: '+447123456789'
      } as AddContactUrn,
      'whatsapp'
    );

    helper.testAction(
      {
        uuid: 'test-action-3',
        type: 'add_contact_urn',
        scheme: 'facebook',
        path: '1234567890'
      } as AddContactUrn,
      'facebook-id'
    );

    helper.testAction(
      {
        uuid: 'test-action-4',
        type: 'add_contact_urn',
        scheme: 'telegram',
        path: '987654321'
      } as AddContactUrn,
      'telegram-id'
    );

    helper.testAction(
      {
        uuid: 'test-action-5',
        type: 'add_contact_urn',
        scheme: 'instagram',
        path: 'user_instagram_handle'
      } as AddContactUrn,
      'instagram-handle'
    );

    helper.testAction(
      {
        uuid: 'test-action-6',
        type: 'add_contact_urn',
        scheme: 'tel',
        path: '@run.results.phone_number'
      } as AddContactUrn,
      'expression-phone'
    );

    helper.testAction(
      {
        uuid: 'test-action-7',
        type: 'add_contact_urn',
        scheme: 'facebook',
        path: '@fields.facebook_id'
      } as AddContactUrn,
      'expression-facebook'
    );

    helper.testAction(
      {
        uuid: 'test-action-8',
        type: 'add_contact_urn',
        scheme: 'line',
        path: 'U1234567890abcdef1234567890abcdef'
      } as AddContactUrn,
      'line-id'
    );

    helper.testAction(
      {
        uuid: 'test-action-9',
        type: 'add_contact_urn',
        scheme: 'viber',
        path: '0123456789ABC='
      } as AddContactUrn,
      'viber-id'
    );

    helper.testAction(
      {
        uuid: 'test-action-10',
        type: 'add_contact_urn',
        scheme: 'wechat',
        path: 'wechatuser123'
      } as AddContactUrn,
      'wechat-id'
    );
  });

  describe('validation', () => {
    it('validates that scheme is required', () => {
      const formData = {
        scheme: [],
        path: '+12065551212'
      };

      const result = add_contact_urn.validate!(formData);

      expect(result.valid).to.be.false;
      expect(result.errors.scheme).to.equal('URN type is required');
    });

    it('validates that path is required', () => {
      const formData = {
        scheme: [{ name: 'Phone Number', value: 'tel' }],
        path: ''
      };

      const result = add_contact_urn.validate!(formData);

      expect(result.valid).to.be.false;
      expect(result.errors.path).to.equal('URN value is required');
    });

    it('validates that path with only whitespace is invalid', () => {
      const formData = {
        scheme: [{ name: 'Phone Number', value: 'tel' }],
        path: '   '
      };

      const result = add_contact_urn.validate!(formData);

      expect(result.valid).to.be.false;
      expect(result.errors.path).to.equal('URN value is required');
    });

    it('validates successfully with both scheme and path', () => {
      const formData = {
        scheme: [{ name: 'Phone Number', value: 'tel' }],
        path: '+12065551212'
      };

      const result = add_contact_urn.validate!(formData);

      expect(result.valid).to.be.true;
      expect(Object.keys(result.errors)).to.have.lengthOf(0);
    });

    it('validates successfully with expression in path', () => {
      const formData = {
        scheme: [{ name: 'Facebook ID', value: 'facebook' }],
        path: '@fields.facebook_id'
      };

      const result = add_contact_urn.validate!(formData);

      expect(result.valid).to.be.true;
      expect(Object.keys(result.errors)).to.have.lengthOf(0);
    });
  });

  describe('round-trip transformation', () => {
    it('should preserve action structure through toFormData -> fromFormData', () => {
      const originalAction: AddContactUrn = {
        uuid: 'test-uuid-123',
        type: 'add_contact_urn',
        scheme: 'whatsapp',
        path: '+447123456789'
      };

      const formData = add_contact_urn.toFormData!(originalAction);
      const convertedAction = add_contact_urn.fromFormData!(
        formData
      ) as AddContactUrn;

      expect(convertedAction.uuid).to.equal(originalAction.uuid);
      expect(convertedAction.type).to.equal(originalAction.type);
      expect(convertedAction.scheme).to.equal(originalAction.scheme);
      expect(convertedAction.path).to.equal(originalAction.path);
    });

    it('should handle different URN schemes correctly', () => {
      const schemes = ['tel', 'facebook', 'telegram', 'instagram', 'whatsapp'];

      schemes.forEach((scheme) => {
        const originalAction: AddContactUrn = {
          uuid: 'test-uuid',
          type: 'add_contact_urn',
          scheme: scheme,
          path: 'test-value'
        };

        const formData = add_contact_urn.toFormData!(originalAction);
        const convertedAction = add_contact_urn.fromFormData!(
          formData
        ) as AddContactUrn;

        expect(convertedAction.scheme).to.equal(scheme);
      });
    });

    it('should handle expressions in path', () => {
      const originalAction: AddContactUrn = {
        uuid: 'test-uuid',
        type: 'add_contact_urn',
        scheme: 'tel',
        path: '@run.results.phone_number'
      };

      const formData = add_contact_urn.toFormData!(originalAction);
      const convertedAction = add_contact_urn.fromFormData!(
        formData
      ) as AddContactUrn;

      expect(convertedAction.path).to.equal('@run.results.phone_number');
    });

    it('should default to tel scheme if scheme is missing in form data', () => {
      const formData = {
        uuid: 'test-uuid',
        scheme: [],
        path: '+12065551212'
      };

      const convertedAction = add_contact_urn.fromFormData!(
        formData
      ) as AddContactUrn;

      expect(convertedAction.scheme).to.equal('tel');
    });
  });

  describe('form data structure', () => {
    it('should convert scheme to select array format in toFormData', () => {
      const action: AddContactUrn = {
        uuid: 'test-uuid',
        type: 'add_contact_urn',
        scheme: 'whatsapp',
        path: '+447123456789'
      };

      const formData = add_contact_urn.toFormData!(action);

      expect(formData.scheme).to.be.an('array');
      expect(formData.scheme).to.have.lengthOf(1);
      expect(formData.scheme[0]).to.deep.include({
        name: 'WhatsApp Number',
        value: 'whatsapp'
      });
    });

    it('should handle unknown scheme gracefully', () => {
      const action: AddContactUrn = {
        uuid: 'test-uuid',
        type: 'add_contact_urn',
        scheme: 'unknown_scheme',
        path: 'some-value'
      };

      const formData = add_contact_urn.toFormData!(action);

      expect(formData.scheme).to.be.null;
    });
  });
});
