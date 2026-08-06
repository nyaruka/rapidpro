import { expect } from '@open-wc/testing';
import { set_contact_language } from '../../src/flow/actions/set_contact_language';
import { SetContactLanguage } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

/**
 * Test suite for the set_contact_language action configuration.
 */
describe('set_contact_language action config', () => {
  const helper = new ActionTest(set_contact_language, 'set_contact_language');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(set_contact_language.name).to.equal('Update Language');
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-action-1',
        type: 'set_contact_language',
        language: 'eng'
      } as SetContactLanguage,
      'english'
    );

    helper.testAction(
      {
        uuid: 'test-action-2',
        type: 'set_contact_language',
        language: 'fra'
      } as SetContactLanguage,
      'french'
    );
  });

  describe('round-trip', () => {
    it('should extract language code from select option', () => {
      const formData = {
        uuid: 'test-uuid',
        language: [{ value: 'spa', name: 'Spanish' }]
      };

      const action = set_contact_language.fromFormData(
        formData
      ) as SetContactLanguage;

      expect(action.language).to.equal('spa');
      expect(action.type).to.equal('set_contact_language');
    });
  });
});
