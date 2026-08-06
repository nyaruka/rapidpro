import { assert } from '@open-wc/testing';
import { Tip } from '../src/display/Tip';
import { assertScreenshot, getClip, getComponent } from './utils.test';

const TAG = 'temba-tip';

const getTarget = () => {
  return "<div style='line-height:0px;font-size:14px;background:green;display:flex'>👱‍♀️</div>";
};

const getTip = async (
  attrs: { text?: string; position?: string; visible?: boolean } = {},
  slot = getTarget()
) => {
  const tip = (await getComponent(
    TAG,
    attrs,
    slot,
    20,
    0,
    'margin:200px;'
  )) as Tip;
  await tip.updateComplete;
  return tip;
};

const getRightClip = (ele: HTMLElement) => {
  const clip = getClip(ele);
  clip.width += 78;
  clip.height += 10;
  clip.y -= 5;
  return clip;
};

const getLeftClip = (ele: HTMLElement) => {
  const clip = getClip(ele);
  clip.x -= 80;
  clip.width += 78;
  clip.height += 10;
  clip.y -= 5;
  return clip;
};

const getTopClip = (ele: HTMLElement) => {
  const clip = getClip(ele);
  clip.y -= 30;
  clip.height += 30;
  clip.width += 30;
  clip.x -= 15;
  return clip;
};

const getBottomClip = (ele: HTMLElement) => {
  const clip = getClip(ele);
  clip.height += 35;
  clip.width += 30;
  clip.x -= 15;
  return clip;
};

describe(TAG, () => {
  it('can be created', async () => {
    const icon = await getTip({ text: 'Resolve' });
    assert.instanceOf(icon, Tip);
  });

  it('shows on the left', async () => {
    const tip = await getTip({
      text: 'Hello!',
      visible: true,
      position: 'left'
    });
    await assertScreenshot('tip/left', getLeftClip(tip));
  });

  it('shows on the right', async () => {
    const tip = await getTip({
      text: 'Hello!',
      visible: true,
      position: 'right'
    });
    await assertScreenshot('tip/right', getRightClip(tip));
  });

  it('shows on top', async () => {
    const tip = await getTip({
      text: 'Hello!',
      visible: true,
      position: 'top'
    });
    await assertScreenshot('tip/top', getTopClip(tip));
  });

  it('shows on bottom', async () => {
    const tip = await getTip({
      text: 'Hello!',
      visible: true,
      position: 'bottom'
    });
    await assertScreenshot('tip/bottom', getBottomClip(tip));
  });
});
