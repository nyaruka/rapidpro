import { fixture } from '@open-wc/testing';
import { CharCount } from '../src/display/CharCount';
import { assertScreenshot, getClip } from './utils.test';

const parentNode = document.createElement('div');
parentNode.setAttribute('style', ' width: 250px;');

const getCharCount = async (html: string) => {
  const counter: CharCount = await fixture(html, { parentNode });
  return counter;
};

describe('temba-charcount', () => {
  it('counts plain text', async () => {
    const counter = await getCharCount(
      "<temba-charcount text='count this text'></temba-charcount>"
    );
    await assertScreenshot('counter/text', getClip(counter));
  });

  it('counts variables', async () => {
    const counter: CharCount = await getCharCount(
      "<temba-charcount text='hi @contact.name'></temba-charcount>"
    );
    // assert(counter).instanceOf(CharCount);
    await assertScreenshot('counter/variable', getClip(counter));
  });

  it('counts unicode', async () => {
    const counter: CharCount = await getCharCount(
      "<temba-charcount text='Messages with 🎱 count extra segments after 70 characters. This message should show two segments.'></temba-charcount>"
    );
    await assertScreenshot('counter/unicode', getClip(counter));
  });

  it('counts unicode with variables', async () => {
    const counter: CharCount = await getCharCount(
      "<temba-charcount text='@contact.name with 🎱 count extra segments after 70 characters. This message should show two segments.'></temba-charcount>"
    );
    await assertScreenshot('counter/unicode-variables', getClip(counter));
  });

  it('shows hover summary', async () => {
    const counter: CharCount = await getCharCount(
      "<temba-charcount text='@contact.name with 🎱 count extra segments after 70 characters. This message should show two segments.'></temba-charcount>"
    );

    const page = window as any;

    // make room for our summary in the screenshot
    const clip = getClip(counter);
    clip.height = 250;

    // move our mouse over the count to show the summary
    await page.moveMouse(clip.right - 15, clip.top + 15);
    await assertScreenshot('counter/summary', clip);

    // put our cursor back in the corner
    await page.moveMouse(0, 0);
  });
});
