import { html, fixture, expect } from '@open-wc/testing';
import { TemplateResult } from 'lit';
import { TembaSlider } from '../src/form/TembaSlider';
import {
  assertScreenshot,
  getClip,
  showMouse,
  waitForAnimations
} from './utils.test';

const createSlider = async (def: TemplateResult) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 200px;');
  return await fixture<TembaSlider>(def, { parentNode });
};

// the circle scales up while it is grabbed and eases back over 200ms once it
// is let go, so releasing the mouse leaves it mid-transition
const settle = async (slider: TembaSlider) => {
  await slider.updateComplete;
  await waitForAnimations(slider.shadowRoot.querySelector('.circle'));
};

describe('temba-slider', () => {
  it('renders default slider', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider"></temba-slider>
    `);

    await assertScreenshot('slider/default', getClip(slider));
  });

  it('renders a slider with visible range - custom min default max no value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" min="5" range></temba-slider>
    `);
    expect(slider.range).to.equal(true);
    expect(slider.min).to.equal(5);
    expect(slider.max).to.equal(100);
    expect(slider.value).to.equal('5');
    await assertScreenshot(
      'slider/custom-min-default-max-no-value',
      getClip(slider)
    );
  });

  it('renders a slider with visible range - default min custom max no value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" max="105" range></temba-slider>
    `);
    expect(slider.range).to.equal(true);
    expect(slider.min).to.equal(0);
    expect(slider.max).to.equal(105);
    expect(slider.value).to.equal('0');
    await assertScreenshot(
      'slider/default-min-custom-max-no-value',
      getClip(slider)
    );
  });

  it('renders a slider with visible range - custom min custom max no value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" min="5" max="105" range></temba-slider>
    `);
    expect(slider.range).to.equal(true);
    expect(slider.min).to.equal(5);
    expect(slider.max).to.equal(105);
    expect(slider.value).to.equal('5');
    await assertScreenshot(
      'slider/default-min-default-max-valid-value',
      getClip(slider)
    );
  });

  it('renders a slider with visible range - custom min custom max valid value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider
        label="My Slider"
        min="5"
        max="105"
        value="55"
        range
      ></temba-slider>
    `);
    expect(slider.range).to.equal(true);
    expect(slider.min).to.equal(5);
    expect(slider.max).to.equal(105);
    expect(slider.value).to.equal('55');
    await assertScreenshot(
      'slider/custom-min-custom-max-valid-value',
      getClip(slider)
    );
  });

  it('renders a slider with visible range - custom min custom max invalid value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider
        label="My Slider"
        min="5"
        max="105"
        value="150"
        range
      ></temba-slider>
    `);
    expect(slider.range).to.equal(true);
    expect(slider.min).to.equal(5);
    expect(slider.max).to.equal(105);
    expect(slider.value).to.equal('105');
    await assertScreenshot(
      'slider/default-min-default-max-invalid-value',
      getClip(slider)
    );
  });

  it('renders a slider without visible range - default min default max no value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider"></temba-slider>
    `);
    expect(slider.range).to.equal(false);
    expect(slider.min).to.equal(0);
    expect(slider.max).to.equal(100);
    expect(slider.value).to.equal('0');
    await assertScreenshot('slider/no-visible-range-no-value', getClip(slider));
  });

  it('renders a slider without visible range - default min default max valid value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" value="50"></temba-slider>
    `);
    expect(slider.range).to.equal(false);
    expect(slider.min).to.equal(0);
    expect(slider.max).to.equal(100);
    expect(slider.value).to.equal('50');
    await assertScreenshot(
      'slider/no-visible-range-valid-value',
      getClip(slider)
    );
  });

  it('renders a slider without visible range - default min default max invalid value', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" value="150"></temba-slider>
    `);
    expect(slider.range).to.equal(false);
    expect(slider.min).to.equal(0);
    expect(slider.max).to.equal(100);
    expect(slider.value).to.equal('100');
    await assertScreenshot(
      'slider/no-visible-range-invalid-value',
      getClip(slider)
    );
  });

  it('updates slider position on element value change', async () => {
    const slider: TembaSlider = await createSlider(html`
      <temba-slider
        label="My Slider"
        min="0"
        max="100"
        value="50"
        range
      ></temba-slider>
    `);
    slider.value = '75';
    expect(slider.value).to.equal('75');
    await assertScreenshot(
      'slider/update-slider-on-value-change',
      getClip(slider)
    );
  });

  it('updates slider position on when track clicked', async () => {
    showMouse();

    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" value="50"></temba-slider>
    `);
    const clip = slider.getBoundingClientRect();

    const y = clip.top + clip.height / 2;
    const x75 = clip.left + (clip.width / 4) * 3;

    // click track at three quarters
    await moveMouse(x75, y);
    await mouseDown();
    await mouseUp();

    expect(slider.value).to.equal('75');
    await settle(slider);
    await assertScreenshot(
      'slider/update-slider-on-track-clicked',
      getClip(slider)
    );
  });

  it('updates slider position on circle drag', async () => {
    showMouse();

    const slider: TembaSlider = await createSlider(html`
      <temba-slider label="My Slider" value="0"></temba-slider>
    `);
    const clip = slider.getBoundingClientRect();

    // hover over the circle at 0, mouse down, then drag to 80
    const y = clip.top + clip.height / 2;
    const x80 = clip.left + (clip.width / 5) * 4;

    await moveMouse(clip.left, y);
    await mouseDown();
    await moveMouse(x80, y);
    await mouseUp();

    expect(slider.value).to.equal('80');
    await settle(slider);
    await assertScreenshot(
      'slider/update-slider-on-circle-dragged',
      getClip(slider)
    );
  });
});
