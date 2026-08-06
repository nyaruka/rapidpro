import { expect, fixture } from '@open-wc/testing';
import { FieldManager } from '../src/live/FieldManager';
import { TextInput } from '../src/form/TextInput';
import {
  assertScreenshot,
  getAttributes,
  getClip,
  loadStore
} from './utils.test';

export const getEle = async (attrs: any = {}) => {
  const fm = `<temba-field-manager
    ${getAttributes(attrs)}
  ></temba-field-manager>`;
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 600px;');
  return (await fixture(fm, { parentNode })) as FieldManager;
};

describe('temba-field-manager', () => {
  it('renders default', async () => {
    await loadStore();
    const fm: FieldManager = await getEle();
    await assertScreenshot('list/fields', getClip(fm));
  });

  it('filters', async () => {
    await loadStore();
    const fm: FieldManager = await getEle();
    (fm.shadowRoot.querySelector('#search') as TextInput).focus();
    fm.query = 'at';
    await fm.updateComplete;
    expect(fm.featuredFields.length).to.equal(1);
    expect(fm.otherFieldKeys.length).to.equal(2);
    await assertScreenshot('list/fields-filtered', getClip(fm));
  });

  it('hovers', async () => {
    await loadStore();
    const fm: FieldManager = await getEle();

    // hover over the first item
    const first = fm.shadowRoot.querySelector('.sortable') as HTMLDivElement;
    const bounds = first.getBoundingClientRect();
    await moveMouse(bounds.left + 20, bounds.top + 10);
    await assertScreenshot('list/fields-hovered', getClip(fm));
  });

  it('drags featured down', async () => {
    await loadStore();
    const fm: FieldManager = await getEle();
    const first = fm.shadowRoot.querySelector('.sortable') as HTMLDivElement;
    const bounds = first.getBoundingClientRect();

    // drag our item
    await moveMouse(bounds.left + 20, bounds.top + 10);
    await mouseDown();
    await moveMouse(bounds.left + 30, bounds.bottom + 20);
    await assertScreenshot('list/fields-dragging', getClip(fm));
  });
});
