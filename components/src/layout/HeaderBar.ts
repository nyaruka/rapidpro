import { css, html, TemplateResult } from 'lit';
import { RapidElement } from '../RapidElement';
import { designTokens } from '../styles/designTokens';

/**
 * A fixed-height header strip with a full-bleed rule under it, for the
 * chat + cards pages (contact read, tickets). Pages can use several side
 * by side (e.g. one over a list column, one over the chat) — the shared
 * height and surface make them read as one continuous control.
 */
export class HeaderBar extends RapidElement {
  static get styles() {
    return css`
      ${designTokens}

      :host {
        /* The single source for the bar's inset — it sets the horizontal
           padding here and, for fit-content bars, the vertical padding the
           slotted page header inherits. Both axes move together by
           construction, so the surround can't drift. */
        --header-bar-inset: 8px;

        flex: 0 0 auto;
        display: flex;
        align-items: center;
        /* 52px strip plus the 1px rule */
        height: var(--header-h);
        box-sizing: border-box;
        padding: 0 var(--header-bar-inset);
        background: var(--surface);
        /* the rule is a box-shadow, not a border — host pages (tailwind
           preflight) reset border-width on every element, and outer-scope
           element styles beat :host */
        box-shadow: inset 0 -1px 0 0 var(--border);
      }

      /* Standalone page headers keep the strip height as a floor but grow
         for taller content (a subtitle), with the same surround on every
         side either way.

         The inset is solved for rather than picked: it's the padding that
         makes inset + one title line + inset come out at exactly the strip
         height, so a single-line title fills the strip with balanced
         spacing. That's why the floor is expressed as height, not as a
         min-height the padding has to fight — with the inset derived this
         way the content already meets the floor, so there's never slack for
         flex centering to absorb into an uneven gap above and below. */
      :host([fit-content]) {
        --header-bar-inset: calc((var(--header-h) - var(--title-line)) / 2);
        --page-header-padding: var(--header-bar-inset) 0;

        align-items: stretch;
        height: auto;
        min-height: var(--header-h);
      }

      ::slotted(*) {
        flex-grow: 1;
        min-width: 0;
      }
    `;
  }

  public render(): TemplateResult {
    return html`<slot></slot>`;
  }
}
