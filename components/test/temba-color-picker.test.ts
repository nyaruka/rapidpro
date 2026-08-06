import { assert } from '@open-wc/testing';
import { ColorPicker } from '../src/form/ColorPicker';
import { assertScreenshot, getClip, getComponent } from './utils.test';

const TAG = 'temba-color-picker';
const getPicker = async (attrs: any = {}) => {
  const picker = (await getComponent(TAG, attrs, '', 400)) as ColorPicker;
  return picker;
};

describe('temba-color-picker', () => {
  it('renders default', async () => {
    const picker: ColorPicker = await getPicker({
      name: 'primary',
      label: 'Primary Color'
    });
    assert.instanceOf(picker, ColorPicker);
    await assertScreenshot('colorpicker/default', getClip(picker));
  });

  it('initializes value', async () => {
    const picker: ColorPicker = await getPicker({
      name: 'primary',
      label: 'Primary Color',
      value: '#2387ca'
    });
    await assertScreenshot('colorpicker/initialized', getClip(picker));
  });

  it('shows spectrum picker', async () => {
    const picker: ColorPicker = await getPicker({
      name: 'primary',
      label: 'Primary Color',
      value: '#2387ca'
    });
    (picker.shadowRoot.querySelector('.preview') as HTMLElement).click();

    await assertScreenshot('colorpicker/focused', getClip(picker), true);
  });

  it('selects color', async () => {
    const picker: ColorPicker = await getPicker({
      name: 'primary',
      label: 'Primary Color',
      value: '#2387ca'
    });
    (picker.shadowRoot.querySelector('.preview') as HTMLElement).click();

    const clip = getClip(picker);

    // move our mouse over the count to show the summary
    const page = window as any;
    await page.mouseClick(clip.left + 200, clip.top + 35);

    await assertScreenshot('colorpicker/selected', getClip(picker), true);
  });
});
