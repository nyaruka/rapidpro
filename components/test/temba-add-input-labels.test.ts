import { fixture, expect } from '@open-wc/testing';
import { html } from 'lit';
import { NodeEditor } from '../src/flow/NodeEditor';
import { AddInputLabels } from '../src/store/flow-definition';

// Register the component
customElements.define('temba-node-editor', NodeEditor);

describe('add_input_labels action editor', () => {
  it('renders form editor for add_input_labels action', async () => {
    const action: AddInputLabels = {
      uuid: 'test-action-uuid',
      type: 'add_input_labels',
      labels: [
        { uuid: 'label-1', name: 'Important' },
        { uuid: 'label-2', name: 'Spam' }
      ]
    };

    const el = (await fixture(html`
      <temba-node-editor .action=${action} .isOpen=${true}></temba-node-editor>
    `)) as NodeEditor;

    await el.updateComplete;
    expect(el.shadowRoot).to.not.be.null;
    expect(el.action).to.equal(action);
  });

  it('can create new labels through the multi-select', async () => {
    const action: AddInputLabels = {
      uuid: 'test-action-uuid',
      type: 'add_input_labels',
      labels: []
    };

    const el = (await fixture(html`
      <temba-node-editor .action=${action} .isOpen=${true}></temba-node-editor>
    `)) as NodeEditor;

    await el.updateComplete;

    // Find the select element for labels
    const selectElement = el.shadowRoot?.querySelector(
      'temba-select[name="labels"]'
    );
    expect(selectElement).to.not.be.null;

    // Verify it has the correct configuration (no longer checking for tags)
    expect(selectElement?.getAttribute('multi')).to.not.be.null;
    expect(selectElement?.getAttribute('searchable')).to.not.be.null;
    expect(selectElement?.getAttribute('endpoint')).to.equal(
      '/api/v2/labels.json'
    );
  });

  it('transforms form data correctly', async () => {
    const action: AddInputLabels = {
      uuid: 'test-action-uuid',
      type: 'add_input_labels',
      labels: [
        { uuid: 'label-1', name: 'Important' },
        { uuid: 'label-2', name: 'Follow Up' }
      ]
    };

    const el = (await fixture(html`
      <temba-node-editor .action=${action} .isOpen=${true}></temba-node-editor>
    `)) as NodeEditor;

    await el.updateComplete;

    // Test toFormData transformation
    const expectedFormData = {
      labels: [
        { uuid: 'label-1', name: 'Important' },
        { uuid: 'label-2', name: 'Follow Up' }
      ],
      uuid: 'test-action-uuid'
    };

    // Access the private formData property
    const formData = (el as any).formData;
    expect(formData).to.not.be.undefined;
    expect(formData.labels).to.deep.equal(expectedFormData.labels);
    expect(formData.uuid).to.equal(expectedFormData.uuid);
  });
});
