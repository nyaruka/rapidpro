import { html } from 'lit-html';
import { ActionConfig, ACTION_GROUPS, FormData, FlowTypes } from '../types';
import { Node, SetContactName } from '../../store/flow-definition';
import { renderClamped, renderHighlightedText } from '../utils';

export const set_contact_name: ActionConfig = {
  name: 'Update Name',
  group: ACTION_GROUPS.contacts,
  flowTypes: [FlowTypes.VOICE, FlowTypes.MESSAGE, FlowTypes.BACKGROUND],
  render: (_node: Node, action: SetContactName) => {
    return renderClamped(
      html`Set to ${renderHighlightedText(action.name, true)}`,
      `Set to ${action.name}`
    );
  },
  form: {
    name: {
      type: 'text',
      label: 'Name',
      placeholder: 'Enter contact name...',
      required: true,
      evaluated: true,
      maxLength: 1000,
      helpText:
        'The new name for the contact. You can use expressions like @contact.name'
    }
  },
  sanitize: (formData: FormData): void => {
    if (formData.name && typeof formData.name === 'string') {
      formData.name = formData.name.trim();
    }
  }
};
