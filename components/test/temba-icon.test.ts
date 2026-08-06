import { assert } from '@open-wc/testing';
import { VectorIcon } from '../src/display/Icon';
import { getComponent } from './utils.test';

const TAG = 'temba-icon';
const getIcon = async (attrs: any = {}) => {
  return (await getComponent(TAG, attrs)) as VectorIcon;
};

describe(TAG, () => {
  it('can be created', async () => {
    const icon = await getIcon({ name: 'checkmark' });
    assert.instanceOf(icon, VectorIcon);
  });
});
