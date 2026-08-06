import { html } from 'lit-html';
import { ActionConfig, ACTION_GROUPS, FormData } from '../types';
import { Node, RequestOptin } from '../../store/flow-definition';
import { renderClamped } from '../utils';

export const request_optin: ActionConfig = {
  name: 'Request Opt-In',
  group: ACTION_GROUPS.send,
  flowTypes: [],
  render: (_node: Node, action: RequestOptin) => {
    const optinName = action.optin?.name || 'Unknown opt-in';
    return renderClamped(
      html`Request <strong>${optinName}</strong>`,
      `Request ${optinName}`
    );
  },
  toFormData: (action: RequestOptin) => {
    return {
      uuid: action.uuid,
      optin: action.optin ? [action.optin] : null
    };
  },
  form: {
    optin: {
      type: 'select',
      label: 'Opt-In',
      required: true,
      searchable: true,
      endpoint: '/api/v2/optins.json',
      valueKey: 'uuid',
      nameKey: 'name',
      placeholder: 'Search for opt-ins or type to create one...',
      helpText:
        'Select an existing opt-in to request, or type a name to create a new one.',
      allowCreate: true,
      createArbitraryOption: (input: string, options: any[]) => {
        const existing = options.find(
          (option) =>
            option.name.toLowerCase().trim() === input.toLowerCase().trim()
        );
        if (!existing && input.trim()) {
          return {
            name: input.trim(),
            arbitrary: true
          };
        }
        return null;
      }
    }
  },
  fromFormData: (formData: FormData): RequestOptin => {
    const optin = formData.optin?.[0];
    return {
      uuid: formData.uuid,
      type: 'request_optin',
      optin: {
        uuid: optin.uuid || optin.value,
        name: optin.name
      }
    };
  }
};
