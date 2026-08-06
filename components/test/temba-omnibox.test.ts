import { fixture, assert } from '@open-wc/testing';
import { Omnibox } from '../src/form/select/Omnibox';
import { assertScreenshot, getClip, openAndClick } from './utils.test';
import { useFakeTimers, spy } from 'sinon';

export const getHTML = (attrs: any = { name: 'recipients' }): string => {
  const selectHTML = `
  <temba-omnibox${Object.keys(attrs)
    .map((name: string) => {
      // check if it's a string attribute
      if (typeof attrs[name] === 'string') {
        return ` ${name}="${attrs[name].replace(/"/g, '&quot;')}"`;
      }
      return ` ${name}="${attrs[name]}"`;
    })
    .join(' ')}>
  </temba-select>`;
  return selectHTML;
};

export const createOmnibox = async (
  clock: any,
  attrs: any = {}
): Promise<Omnibox> => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 400px;');

  const omnibox: Omnibox = await fixture(getHTML(attrs), { parentNode });
  clock.runAll();
  await omnibox.updateComplete;
  return omnibox;
};

describe('temba-omnibox', () => {
  let clock: any;
  beforeEach(function () {
    clock = useFakeTimers();
    setViewport({ width: 500, height: 1000, deviceScaleFactor: 2 });
  });

  afterEach(function () {
    clock.restore();
  });

  it('can be created', async () => {
    const omnibox: Omnibox = await fixture(
      getHTML({ endpoint: '/test-assets/select/omnibox.json' })
    );
    assert.instanceOf(omnibox, Omnibox);
  });

  // TODO: make this pass reliably on CI
  xit('fires change events on selection', async () => {
    const omnibox: Omnibox = await createOmnibox(clock, {
      endpoint: '/test-assets/select/omnibox.json'
    });

    const changeEvent = spy();
    omnibox.addEventListener('change', changeEvent);

    clock.runAll();
    await omnibox.updateComplete;
    clock.runAll();

    await openAndClick(clock, omnibox, 0);
    clock.runAll();
    assert(changeEvent.called, 'change event not fired');

    await assertScreenshot('omnibox/selected', getClip(omnibox));
  });
});
