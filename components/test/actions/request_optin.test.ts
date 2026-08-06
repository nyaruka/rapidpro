import { expect } from '@open-wc/testing';
import { request_optin } from '../../src/flow/actions/request_optin';
import { RequestOptin } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';

describe('request_optin action config', () => {
  const helper = new ActionTest(request_optin, 'request_optin');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(request_optin.name).to.equal('Request Opt-In');
    });

    it('uses the opt-ins endpoint in form config', () => {
      expect((request_optin.form as any).optin.endpoint).to.equal(
        '/api/v2/optins.json'
      );
    });
  });

  it('converts action to form data correctly', () => {
    const action: RequestOptin = {
      uuid: 'action-uuid',
      type: 'request_optin',
      optin: { uuid: 'optin-1', name: 'U-Report' }
    };

    const formData = request_optin.toFormData(action);

    expect(formData.uuid).to.equal('action-uuid');
    expect(formData.optin).to.deep.equal([
      { uuid: 'optin-1', name: 'U-Report' }
    ]);
  });

  it('converts form data back to action and strips metadata', () => {
    const formData = {
      uuid: 'action-uuid',
      optin: [
        {
          uuid: 'optin-1',
          name: 'U-Report',
          created_on: '2026-02-24T19:08:29.493930Z',
          is_active: true
        }
      ]
    };

    const action = request_optin.fromFormData(formData) as RequestOptin;

    expect(action).to.deep.equal({
      uuid: 'action-uuid',
      type: 'request_optin',
      optin: { uuid: 'optin-1', name: 'U-Report' }
    });
  });

  it('handles options selected via value key', () => {
    const formData = {
      uuid: 'action-uuid',
      optin: [
        {
          value: 'optin-2',
          name: 'Re-Subscribe'
        }
      ]
    };

    const action = request_optin.fromFormData(formData) as RequestOptin;

    expect(action.optin).to.deep.equal({
      uuid: 'optin-2',
      name: 'Re-Subscribe'
    });
  });
});
