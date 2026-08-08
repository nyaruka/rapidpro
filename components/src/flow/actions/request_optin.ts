import { html } from 'lit-html';
import { ActionConfig, ACTION_GROUPS } from '../types';
import { Node, RequestOptin } from '../../store/flow-definition';
import { renderClamped } from '../utils';

// Opt-ins are no longer a supported concept — this config exists only so
// that actions left behind in older flow definitions still render. It has
// no form, which makes the action read-only in the editor.
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
  }
};
