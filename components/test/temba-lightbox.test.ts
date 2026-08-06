import { fixture, assert, expect } from '@open-wc/testing';
import { Lightbox } from '../src/display/Lightbox';
import { Thumbnail } from '../src/display/Thumbnail';
import { assertScreenshot, delay } from './utils.test';

export const getHTML = () => {
  return `<temba-lightbox animationTime="0"></temba-lightbox>`;
};

describe('temba-lightbox', () => {
  before(async () => {
    // match the viewport to the screenshot clip so the centered, contained
    // image is fully captured (the shared default is 1920x1080)
    await (window as any).setViewport({
      width: 1024,
      height: 768,
      deviceScaleFactor: 2
    });
  });

  after(async () => {
    // restore the shared default set in utils.test.ts's global before()
    await (window as any).setViewport({
      width: 1920,
      height: 1080,
      deviceScaleFactor: 2
    });
  });

  it('can be created', async () => {
    const lightbox: Lightbox = await fixture(getHTML());
    const img = await fixture(
      "<img style='width:100px;height:auto' src='./test-assets/img/meow.jpg'/>"
    );

    await assertScreenshot('lightbox/img', {
      x: 0,
      y: 0,
      width: 1024,
      height: 768
    });

    assert.instanceOf(lightbox, Lightbox);
    lightbox.showElement(img as HTMLElement);

    // let the mount -> zoom transition settle
    await delay(50);

    // the lightbox shows the clicked image, contained within the viewport
    const shown = lightbox.shadowRoot.querySelector('img') as HTMLImageElement;
    expect(shown, 'lightbox should render the image').to.exist;
    expect(shown.src).to.contain('meow.jpg');
    const rect = shown.getBoundingClientRect();
    expect(rect.width).to.be.at.most(window.innerWidth);
    expect(rect.height).to.be.at.most(window.innerHeight);
    // centered horizontally within a small tolerance
    const centerX = rect.left + rect.width / 2;
    expect(Math.abs(centerX - window.innerWidth / 2)).to.be.lessThan(4);

    await assertScreenshot('lightbox/img-zoomed', {
      x: 0,
      y: 0,
      width: 1024,
      height: 768
    });
  });

  it('shows a temba-thumbnail via its url property', async () => {
    const lightbox: Lightbox = await fixture(getHTML());
    const thumbnail: Thumbnail = await fixture(
      "<temba-thumbnail attachment='image/jpeg:./test-assets/img/meow.jpg'></temba-thumbnail>"
    );
    await thumbnail.updateComplete;

    // a thumbnail has no .src — showElement falls back to its url property
    lightbox.showElement(thumbnail);
    await delay(50);

    const shown = lightbox.shadowRoot.querySelector('img') as HTMLImageElement;
    expect(shown, 'lightbox should render the thumbnail image').to.exist;
    expect(shown.src).to.contain('meow.jpg');
  });

  it('dismisses on backdrop click', async () => {
    const lightbox: Lightbox = await fixture(getHTML());
    const img = await fixture(
      "<img style='width:100px;height:auto' src='./test-assets/img/meow.jpg'/>"
    );

    lightbox.showElement(img as HTMLElement);
    await delay(50);
    expect(lightbox.shadowRoot.querySelector('img')).to.exist;

    const backdrop = lightbox.shadowRoot.querySelector(
      '.backdrop'
    ) as HTMLElement;
    backdrop.click();
    await delay(50);

    // the fade-out has finished and the image is unmounted
    expect(lightbox.zoom).to.equal(false);
    expect(lightbox.show).to.equal(false);
    expect(lightbox.shadowRoot.querySelector('img')).to.not.exist;
  });

  it('swaps images when re-opened during a dismissal', async () => {
    const lightbox: Lightbox = await fixture(
      '<temba-lightbox animationTime="100"></temba-lightbox>'
    );
    const first = await fixture(
      "<img style='width:100px;height:auto' src='./test-assets/img/meow.jpg'/>"
    );
    const second = await fixture(
      "<img style='width:100px;height:auto' src='./test-assets/img/meow.jpg?second'/>"
    );

    lightbox.showElement(first as HTMLElement);
    await delay(50);

    // start dismissing and let the fade-out (and its pending unmount timer)
    // kick off, then open another image mid-fade
    lightbox.handleClick();
    await delay(20);
    lightbox.showElement(second as HTMLElement);

    // wait past the original unmount timer — the re-open must cancel it
    await delay(200);
    const shown = lightbox.shadowRoot.querySelector('img') as HTMLImageElement;
    expect(shown, 'lightbox should still be showing an image').to.exist;
    expect(shown.src).to.contain('meow.jpg?second');
    expect(lightbox.zoom).to.equal(true);
  });
});
