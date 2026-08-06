import { expect, fixture } from '@open-wc/testing';
import { html } from 'lit';
import '../temba-modules';
import { HeaderBar } from '../src/layout/HeaderBar';
import { assertScreenshot, getClip } from './utils.test';

describe('temba-header-bar', () => {
  it('renders a fixed strip with its rule and grows slotted content', async () => {
    const bar = (await fixture(html`
      <temba-header-bar>
        <div id="content">title</div>
      </temba-header-bar>
    `)) as HeaderBar;

    const styles = getComputedStyle(bar);

    // the 52px strip plus its full-bleed 1px rule — an inset box-shadow
    // so host-page border resets (tailwind preflight) can't strip it
    expect(styles.height).to.equal('53px');
    expect(styles.boxShadow).to.contain('inset');
    expect(styles.display).to.equal('flex');

    // slotted content stretches to fill the strip
    const content = bar.querySelector('#content');
    expect(getComputedStyle(content).flexGrow).to.equal('1');
  });

  // The surround is measured from the rendered boxes rather than read off
  // the declared padding — the failure mode being guarded is a height taller
  // than its content, which leaves the declared padding untouched while
  // handing the slack to the gap above and below the title. The gaps are
  // compared against each other, not a hardcoded inset, so restyling the
  // strip height or the title type stays caught by balance alone.
  for (const subtitle of ['', 'Supporting context']) {
    it(`balances the surround of a fit-content title${subtitle ? ' with a subtitle' : ''}`, async () => {
      const bar = (await fixture(html`
        <temba-header-bar fit-content>
          <temba-page-header
            header-title="Knowledge"
            subtitle=${subtitle}
          ></temba-page-header>
        </temba-header-bar>
      `)) as HeaderBar;
      const header = bar.querySelector('temba-page-header') as HTMLElement & {
        updateComplete: Promise<unknown>;
      };
      await header.updateComplete;

      const barBox = bar.getBoundingClientRect();
      const titleBlock = header.shadowRoot.querySelector(
        '.title-block'
      ) as HTMLElement;
      const actions = header.shadowRoot.querySelector(
        '.actions'
      ) as HTMLElement;
      const titleBox = titleBlock.getBoundingClientRect();
      const actionsBox = actions.getBoundingClientRect();

      const above = titleBox.top - barBox.top;
      const below = barBox.bottom - titleBox.bottom;
      const left = titleBox.left - barBox.left;
      const right = barBox.right - actionsBox.right;

      // every side matches the gap above the title
      expect(below, 'below title').to.be.closeTo(above, 0.5);
      expect(left, 'left of title').to.be.closeTo(above, 0.5);
      expect(right, 'right of actions').to.be.closeTo(above, 0.5);

      // the strip height is a floor the content already meets, so it never
      // leaves slack for the centering to turn into an uneven gap
      expect(getComputedStyle(bar).minHeight).to.equal('53px');
      expect(barBox.height).to.be.at.least(53 - 0.5);
      expect(barBox.height, 'height is surround + content').to.be.closeTo(
        titleBox.height + above * 2,
        0.5
      );
    });
  }

  // the geometry assertions above prove the surround is balanced; these
  // record what that actually looks like, so a restyle that keeps the maths
  // true but changes the strip's character still shows up in review
  for (const subtitle of ['', 'Supporting context']) {
    const state = subtitle ? 'subtitle' : 'title-only';
    it(`renders a fit-content bar (${state}, screenshot)`, async () => {
      const bar = (await fixture(html`
        <div style="width: 700px;">
          <temba-header-bar fit-content>
            <temba-page-header
              header-title="Knowledge"
              subtitle=${subtitle}
            ></temba-page-header>
          </temba-header-bar>
        </div>
      `)) as HTMLElement;
      const header = bar.querySelector('temba-page-header') as HTMLElement & {
        updateComplete: Promise<unknown>;
      };
      await header.updateComplete;

      await assertScreenshot(
        `header-bar/fit-content-${state}`,
        getClip(bar.querySelector('temba-header-bar') as HeaderBar)
      );
    });
  }
});
