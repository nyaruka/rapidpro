import '../../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { html } from 'lit-html';
import { request_optin } from '../../src/flow/actions/request_optin';
import { CanvasNode } from '../../src/flow/CanvasNode';
import { Node, RequestOptin } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';
import { loadStore } from '../utils.test';

const NODE: Node = { uuid: 'test-node', actions: [], exits: [] };

const renderAction = (action: RequestOptin): Promise<HTMLElement> =>
  fixture<HTMLElement>(html`<div>${request_optin.render(NODE, action)}</div>`);

describe('request_optin action config', () => {
  const helper = new ActionTest(request_optin, 'request_optin');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(request_optin.name).to.equal('Request Opt-In');
    });

    it('is not offered for any flow type', () => {
      expect(request_optin.flowTypes).to.deep.equal([]);
    });

    it('is not editable', () => {
      expect(request_optin.form).to.be.undefined;
      expect(request_optin.toFormData).to.be.undefined;
      expect(request_optin.fromFormData).to.be.undefined;
    });
  });

  describe('rendering', () => {
    it('renders the opt-in from an existing definition', async () => {
      const host = await renderAction({
        uuid: 'action-uuid',
        type: 'request_optin',
        optin: { uuid: 'optin-1', name: 'U-Report' }
      });

      expect(host.textContent).to.contain('U-Report');
    });

    it('renders a placeholder when the opt-in is missing', async () => {
      const host = await renderAction({
        uuid: 'action-uuid',
        type: 'request_optin'
      } as RequestOptin);

      expect(host.textContent).to.contain('Unknown opt-in');
    });

    // the whole reason this config still exists — a request_optin left
    // behind in an old definition has to draw on the canvas, not throw
    it('renders inside a flow node on the canvas', async () => {
      await loadStore();

      const node = (await fixture(
        '<temba-flow-node></temba-flow-node>'
      )) as CanvasNode;
      (node as any).node = {
        uuid: 'node-1',
        actions: [
          {
            uuid: 'action-uuid',
            type: 'request_optin',
            optin: { uuid: 'optin-1', name: 'U-Report' }
          }
        ],
        exits: [{ uuid: 'exit-1', destination_uuid: null }]
      };
      (node as any).ui = {
        type: 'execute_actions',
        position: { left: 0, top: 0 }
      };
      await node.updateComplete;

      expect(node.textContent).to.contain('U-Report');
    });
  });
});
