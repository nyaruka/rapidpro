import { assert, expect } from '@open-wc/testing';
import { ContactFieldEditor } from '../src/live/ContactFieldEditor';
import { ContactFields } from '../src/live/ContactFields';
import { resetContactWatches } from '../src/live/ContactWatch';
import { setSocketProvider, SocketProvider } from '../src/live/SocketService';
import {
  getComponent,
  loadStore,
  mockGET,
  mockPOST,
  MockSocketProvider,
  waitForCondition,
  waitForWatchedContact
} from './utils.test';

const TAG = 'temba-contact-fields';
const getFields = async (attrs: any = {}) => {
  attrs['endpoint'] = '/test-assets/contacts/';
  attrs['writeEndpoint'] = '/test-assets/contacts/';
  const fields = (await getComponent(TAG, attrs, '', 600)) as ContactFields;

  // wait for our contact data to load
  await waitForCondition(() => !!fields.data);

  return fields;
};

describe(TAG, () => {
  let mockSocket: MockSocketProvider;
  let previousProvider: SocketProvider;

  beforeEach(() => {
    mockSocket = new MockSocketProvider();
    previousProvider = setSocketProvider(mockSocket);
  });

  afterEach(() => {
    resetContactWatches();
    setSocketProvider(previousProvider);
  });

  it('updates live when a field changes', async () => {
    await loadStore();

    // the central watcher fetches its contact from the api
    mockGET(
      /\/api\/v2\/contacts\.json\?expand_urns=true&urn_order=priority&uuid=contact-dave-active/,
      '/test-assets/contacts/contact-dave-active'
    );

    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active'
    });
    assert.equal(fields.data.fields.age, '30');
    await waitForWatchedContact('contact-dave-active');

    // the event's engine value is applied directly, serialized by the
    // field's type - no refetch involved
    mockSocket.serverPublish('history:contact-dave-active', {
      type: 'contact_field_changed',
      field: { key: 'age', name: 'Age' },
      value: { text: '31 years', number: 31 }
    });

    await waitForCondition(() => fields.data.fields.age === '31');
  });

  it('renders default', async () => {
    // we are a StoreElement, so load a store first
    await loadStore();

    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active'
    });
    assert.instanceOf(fields, ContactFields);
    // await assertScreenshot('contacts/fields', getClip(fields));
  });

  it('handles updated contacts properly', async () => {
    await loadStore();
    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active'
    });

    const data = fields.data;
    data.groups.forEach((group) => {
      delete group['is_dynamic'];
    });
    // field updates post to the write endpoint
    mockPOST(/\/test-assets\/contacts\/contact-dave-active/, data);

    // update our fields
    await typeInto(
      "temba-contact-fields:temba-contact-field[key='age']:temba-textinput",
      '62',
      true,
      true
    );

    // the updated contact should still have is_dynamic flags added
    expect(fields.data.groups[0].is_dynamic).equals(true);
    expect(fields.data.groups[1].is_dynamic).equals(false);

    // await assertScreenshot('contacts/fields-updated', getClip(fields));
  });

  it('honors agent field access', async () => {
    const store = await loadStore();
    store.getContactField('gender').agent_access = 'none';
    store.getContactField('age').agent_access = 'view';
    store.getContactField('joined').agent_access = 'edit';

    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active',
      role: 'T'
    });
    await fields.updateComplete;

    expect(fields.shadowRoot.querySelector('temba-contact-field[key="gender"]'))
      .to.be.null;

    const viewOnly = fields.shadowRoot.querySelector(
      'temba-contact-field[key="age"]'
    ) as ContactFieldEditor;
    expect(viewOnly.disabled).to.be.true;
    expect(viewOnly.shadowRoot.querySelector('temba-textinput')).to.be.null;
    expect(viewOnly.shadowRoot.querySelector('.wrapper.disabled')).not.to.be
      .null;

    const editable = fields.shadowRoot.querySelector(
      'temba-contact-field[key="joined"]'
    ) as ContactFieldEditor;
    expect(editable.disabled).to.be.false;
    expect(editable.shadowRoot.querySelector('temba-datepicker')).not.to.be
      .null;

    const fetchCount = (window.fetch as any).callCount;
    viewOnly.value = '41';
    fields.handleFieldChanged({
      currentTarget: viewOnly
    } as unknown as InputEvent);
    expect((window.fetch as any).callCount).to.equal(fetchCount);
  });

  // regression: the contact data and the store's field definitions load
  // independently. if the contact data arrives first (more likely under
  // Firefox's request scheduling) we must not render against missing field
  // definitions, which previously threw and left the tab blank.
  it('does not render or crash before field definitions load', async () => {
    await loadStore();
    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active'
    });

    // simulate the race: contact data present, but definitions not yet loaded
    fields.fieldsReady = false;
    await fields.updateComplete;

    // nothing should render and, crucially, render must not throw
    expect(
      fields.shadowRoot.querySelectorAll('temba-contact-field').length
    ).to.equal(0);

    // once the definitions arrive, the fields populate
    fields.fieldsReady = true;
    await fields.updateComplete;
    expect(
      fields.shadowRoot.querySelectorAll('temba-contact-field').length
    ).to.be.greaterThan(0);
  });

  // regression: a contact may carry a field key whose definition no longer
  // exists (e.g. a deleted field). a single missing definition must not throw
  // and blank out the entire tab.
  it('ignores contact field keys with no matching definition', async () => {
    await loadStore();
    const fields: ContactFields = await getFields({
      contact: 'contact-dave-active'
    });

    const known = fields.shadowRoot.querySelectorAll(
      'temba-contact-field'
    ).length;
    expect(known).to.be.greaterThan(0);

    // inject a field key that has no definition in the store
    fields.data = {
      ...fields.data,
      fields: { ...fields.data.fields, nonexistent_field_xyz: 'orphan value' }
    };
    await fields.updateComplete;

    // render must not throw and the orphan key must be dropped, leaving the
    // known fields intact
    expect(
      fields.shadowRoot.querySelectorAll('temba-contact-field').length
    ).to.equal(known);
  });
});
