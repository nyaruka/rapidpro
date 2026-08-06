import { LitElement, TemplateResult, html, css } from 'lit';
import { property } from 'lit/decorators.js';
import { msg } from '@lit/localize';
import { getClasses } from '../utils';
import { styleMap } from 'lit-html/directives/style-map.js';
import { designTokens } from '../styles/designTokens';
import {
  pillVariants,
  PILL_TYPES,
  PILL_TYPE_ICONS
} from '../styles/pillVariants';

export default class Label extends LitElement {
  static get styles() {
    return css`
      ${designTokens}

      :host {
        display: inline-block;
        /* Cap at parent width so a pill sitting in a constrained
           container (e.g. a flow canvas node body) shrinks to fit
           rather than overflowing. The slot/mask below have the
           min-width:0 needed to let the ellipsis engage. */
        max-width: 100%;
        /* As a flex item the host's automatic minimum size is its
           full nowrap text width, which refuses to shrink and
           stretches content-sized ancestors (e.g. the Next Up card)
           instead of ellipsizing. min-width:0 lets the pill shrink
           to its container so the slot ellipsis can engage. */
        min-width: 0;
      }

      slot {
        white-space: nowrap;
        overflow-x: hidden;
        text-overflow: ellipsis;
        display: block;
        /* min-width:0 lets the slot — as a flex item inside .mask —
           shrink below its content size so the overflow/ellipsis can
           engage. The default is 0 so every label can collapse fully;
           a consumer that wants a squeezed pill to keep a couple of
           characters visible (rather than collapsing to bare chrome)
           opts in by setting --label-min-width (e.g. 2em). */
        min-width: var(--label-min-width, 0);
      }

      .mask {
        padding: 3px 8px;
        border-radius: 12px;
        display: flex;
        /* Same reason as slot — let the mask shrink below its content
           size so the inner slot can ellipsize. */
        min-width: 0;
      }

      temba-icon {
        margin-right: 0.3em;
        padding-bottom: 0.1em;
      }

      .label.clickable .mask:hover {
        background: var(--color-background-hover, rgb(0, 0, 0, 0.05));
      }

      .label {
        font-size: 0.8em;
        font-weight: 400;
        border-radius: 12px;
        box-shadow: var(--widget-shadow, 0 0.04em 0.08em rgba(0, 0, 0, 0.15));
        background: var(--color-overlay-light);
        color: var(--color-overlay-light-text);
        --icon-color: var(--color-overlay-light-text);
        text-shadow: none;
      }

      /* DS pill mode — engaged when the consumer sets [type]. Overrides
         the legacy chip chrome (shadow) and shape (12px radius) with
         the design-system pill (flat, type-colored via .pill-{type},
         1px border, 999px radius). Background/foreground/icon-color
         are owned by pillVariants — we only set non-color chrome here
         so we don't outrank the variant. */
      .label[class*='pill-'] {
        font-size: 11.5px;
        font-weight: var(--w-regular);
        /* border color is owned by .pill-{type} in pillVariants — only
           set width/style here so we don't outrank the variant. */
        border-width: 1px;
        border-style: solid;
        border-radius: 999px;
        box-shadow: none;
      }
      .label[class*='pill-'] .mask {
        padding: 0 7px;
        height: 20px;
        align-items: center;
        gap: 4px;
        border-radius: 999px;
      }
      /* Hover tint pulled from the pill's own foreground (which is the
         dark variant shade), so flow stays bluish, group stays purplish,
         etc. — no grey wash. */
      .label[class*='pill-'].clickable .mask:hover {
        /* Neutral wash first for browsers without color-mix() — the
           currentColor mix can't fall back per-declaration because
           currentColor keeps it valid until computed-value time. */
        background: rgba(0, 0, 0, 0.06);
      }
      .label[class*='pill-'] temba-icon {
        margin-right: 0;
        padding-bottom: 0;
      }

      /* Chip-style X button — matches the multi-select chip's
         .remove-item. currentColor-tinted bg so it picks up the
         pill variant's hue. Sits on the left, ahead of the icon. */
      .label[class*='pill-'] .remove {
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        padding: 0;
        margin: 0;
        border: 0;
        border-radius: 999px;
        background: rgba(0, 0, 0, 0.12);
        color: inherit;
        opacity: 0.8;
        --icon-color: currentColor;
      }
      .label[class*='pill-'] .remove:hover {
        opacity: 1;
        background: rgba(0, 0, 0, 0.22);
      }

      @supports (color: color-mix(in srgb, red, red)) {
        .label[class*='pill-'].clickable .mask:hover {
          background: color-mix(in oklab, currentColor 10%, transparent);
        }
        .label[class*='pill-'] .remove {
          background: color-mix(in oklab, currentColor 25%, transparent);
        }
        .label[class*='pill-'] .remove:hover {
          background: color-mix(in oklab, currentColor 45%, transparent);
        }
      }

      /* When a removable X is present, tighten the mask's left padding
         so the X sits snug against the pill edge (matches the
         multi-select chip's 4px left padding). Right padding stays so
         the trailing icon/name keep their breathing room. */
      .label[class*='pill-']:has(.remove) .mask {
        padding-left: 4px;
      }

      .danger {
        background: tomato;
        color: #fff;
        --icon-color: #fff;
      }

      .primary {
        background: var(--color-primary-dark);
        color: var(--color-text-light);
        --icon-color: var(--color-text-light);
      }

      .secondary {
        background: var(--color-secondary-dark);
        color: var(--color-text-light);
        --icon-color: var(--color-text-light);
      }

      .tertiary {
        background: var(--color-tertiary);
        color: var(--color-text-light);
        --icon-color: var(--color-text-light);
      }

      .dark {
        background: var(--color-overlay-dark);
        text-shadow: none;
      }

      .clickable {
        cursor: pointer;
      }

      .shadow {
        box-shadow: 1px 1px 2px 1px rgba(0, 0, 0, 0.1);
      }

      /* DS pill variants come last so .pill-{type} wins on source
         order against equal-specificity legacy rules above (.label,
         .danger, .primary, etc.). */
      ${pillVariants}
    `;
  }

  @property({ type: Boolean })
  clickable: boolean;

  @property({ type: Boolean })
  primary: boolean;

  @property({ type: Boolean })
  secondary: boolean;

  @property({ type: Boolean })
  tertiary: boolean;

  @property({ type: Boolean })
  danger: boolean;

  @property({ type: Boolean })
  dark: boolean;

  @property({ type: Boolean })
  shadow: boolean;

  @property({ type: String })
  icon: string;

  /**
   * An additional icon rendered ahead of the main icon — e.g. a +/−
   * qualifier on a group pill ("added to" vs "removed from"). Unlike
   * `icon` it never falls back to the type's default, so it only
   * renders when explicitly set.
   */
  @property({ type: String, attribute: 'prefix-icon' })
  prefixIcon: string;

  /**
   * Design-system pill variant — `flow`, `group`, `contact`, `field`,
   * `keyword`, `label`, or `neutral`. When set, switches the chrome to
   * a flat DS pill (rounded 999px, type-colored). Stays the legacy
   * shadowed label when unset, so existing consumers are unaffected.
   */
  @property({ type: String })
  type: string;

  /**
   * Render a chip-style X button on the left of the pill. Clicking it
   * fires a `temba-remove` event; the rest of the pill stays clickable
   * for navigation as usual.
   */
  @property({ type: Boolean })
  removable: boolean;

  /**
   * Accessible label for the remove button. Defaults to a localized
   * "Remove", but consumers whose action verb differs (e.g.
   * "Interrupt flow") should pass their own — the X button is the
   * affordance for whatever action `temba-remove` triggers, so the
   * accessible name should match.
   */
  @property({ type: String })
  removeLabel: string;

  @property()
  backgroundColor: string;

  @property()
  textColor: string;

  private handleRemove(e: MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    this.dispatchEvent(
      new CustomEvent('temba-remove', { bubbles: true, composed: true })
    );
  }

  public render(): TemplateResult {
    const labelStyle = {};

    if (this.backgroundColor) {
      labelStyle['background'] = this.backgroundColor;
    }

    if (this.textColor) {
      labelStyle['color'] = this.textColor;
      labelStyle['--icon-color'] = this.textColor;
    }

    // Only emit `pill-${this.type}` if it's a recognized variant.
    // An unknown value (or one containing whitespace, e.g.
    // `"flow danger"` from a malformed template) would otherwise split
    // into multiple classes and collide with internal modifiers
    // (`.danger`, `.shadow`, `.clickable`, etc.) defined on `.label`.
    const validType = this.type && PILL_TYPES.has(this.type);
    const variantClass = validType ? `pill-${this.type}` : '';
    // When the consumer sets a recognized `type` (group / flow / etc.)
    // but doesn't supply an explicit `icon`, fall back to the type's
    // default icon from PILL_TYPE_ICONS. Call sites then only need
    // `type="group"` instead of `type="group" icon="group"`.
    const resolvedIcon =
      this.icon || (validType ? PILL_TYPE_ICONS[this.type] : undefined);

    const removeAriaLabel = this.removeLabel || msg('Remove');

    return html`
      <div
        class="label ${getClasses({
          clickable: this.clickable,
          primary: this.primary,
          secondary: this.secondary,
          tertiary: this.tertiary,
          shadow: this.shadow,
          danger: this.danger,
          dark: this.dark
        })} ${variantClass}"
        style=${styleMap(labelStyle)}
      >
        <div class="mask">
          ${this.removable
            ? html`<button
                class="remove"
                @click=${this.handleRemove}
                aria-label=${removeAriaLabel}
              >
                <temba-icon name="x" size="0.85"></temba-icon>
              </button>`
            : null}
          ${this.prefixIcon
            ? html`<temba-icon name=${this.prefixIcon} />`
            : null}
          ${resolvedIcon ? html`<temba-icon name=${resolvedIcon} />` : null}
          <slot></slot>
        </div>
      </div>
    `;
  }
}
