import { css } from 'lit';

/**
 * TextIt Design System pill color variants — single source of truth.
 *
 * Provides the color triple (background / foreground / border) keyed
 * off `.pill-{type}` plus the JS-side taxonomy (`PILL_TYPES`,
 * `PILL_TYPE_ICONS`, `iconToPillType`) consumed by Select.ts and
 * flow/utils.ts.
 *
 * Variant theming:
 *   - .pill-contact / .pill-group: derived from --recipient (a fixed
 *     blue), NOT the accent ramp. This keeps recipient pills stable
 *     across brand re-theming via --primary-rgb.
 *   - .pill-flow, .pill-channel: bg/border derived from --flow /
 *     --channel via color-mix; text + icon use the anchor directly.
 *   - .pill-field: bg/border are fixed at the Tailwind yellow ramp
 *     (yellow-100 / yellow-300) because yellow has too little
 *     contrast against white to color-mix into a recognizable swatch.
 *     Text uses yellow-900 for readability; the icon uses --field
 *     directly, which is the only knob a host page can re-theme.
 *   - .pill-neutral / .pill-label / .pill-keyword: greys; not
 *     anchor-driven.
 *
 * Shape (height, padding, radius, icon spacing) is the consumer's
 * concern, since pill use-cases differ: Select chips have a remove
 * button on the right, ContactDetails pills are clickable links, etc.
 *
 * To add a new variant: extend `PILL_TYPES`, optionally add an entry
 * to `PILL_TYPE_ICONS` / `ICON_TO_PILL_TYPE`, append a `.pill-{type}`
 * block below, and reference an anchor in `designTokens.ts`.
 */

/** Recognized pill variants. Anything outside this set falls back to
 * `pill-neutral` (or is rejected by callers as not a pill at all). */
export const PILL_TYPES: ReadonlySet<string> = new Set([
  'neutral',
  'flow',
  'group',
  'contact',
  'field',
  'label',
  'keyword',
  'channel',
  'topic',
  'campaign',
  'removed'
]);

/** Default icon name for each pill variant. Used when a consumer
 * specifies `type` but not `icon` — keeps Omnibox-style options and
 * Django-form-rendered options visually consistent without making the
 * data layer set both fields. */
export const PILL_TYPE_ICONS: Readonly<Record<string, string>> = {
  group: 'group',
  contact: 'contact',
  field: 'fields',
  flow: 'flow',
  label: 'label',
  topic: 'topic',
  campaign: 'campaign'
};

/** Inverse mapping: icon name (alias or resolved SVG id) → pill type.
 * Both forms are valid since flow-action items pass through either. */
const ICON_TO_PILL_TYPE: Readonly<Record<string, string>> = {
  flow: 'flow',
  group: 'group',
  contact: 'contact',
  contacts: 'contact',
  field: 'field',
  fields: 'field',
  label: 'label',
  campaign: 'campaign',
  // resolved Icon enum SVG ids
  'users-01': 'group',
  'atom-01': 'group',
  'user-01': 'contact',
  'tag-01': 'label',
  'clock-refresh': 'campaign'
};

export const iconToPillType = (icon?: string): string | undefined => {
  if (!icon) return undefined;
  if (ICON_TO_PILL_TYPE[icon]) return ICON_TO_PILL_TYPE[icon];
  // Legacy alias prefix (e.g. 'group_smart' → 'group').
  if (icon.startsWith('group')) return 'group';
  return undefined;
};

export const pillVariants = css`
  /* The grey variants border off --pill-border, falling back to
     --border. The indirection lets a host context (e.g. a selected
     list row) retint the border without redefining --border, which
     each component re-declares in its own shadow DOM via the design
     tokens and so can't be overridden from outside. */
  .pill-neutral {
    background: var(--sunken);
    color: var(--text-1);
    border-color: var(--pill-border, var(--border));
    --icon-color: var(--text-2);
  }
  /* Anchor-derived variants carry static pre-mixed bg/border values
     for browsers without color-mix() (pre-Chrome 111); the @supports
     block at the bottom re-derives them from the anchors so host
     re-theming still works where color-mix() is available. */
  .pill-flow {
    background: #e3f4e9;
    color: var(--flow);
    border-color: #c5e8d2;
    --icon-color: var(--flow);
  }
  /* Recipient color — shared by contacts and groups. Anchored to
     --recipient (fixed blue), NOT the accent ramp, so pills keep their
     identity even when the host page re-themes via --primary-rgb. */
  .pill-contact,
  .pill-group {
    background: #e5eef6;
    color: var(--recipient);
    border-color: #cadbec;
    --icon-color: var(--recipient);
  }
  .pill-channel {
    background: #ede4f5;
    color: var(--channel);
    border-color: #dac8e9;
    --icon-color: var(--channel);
  }
  .pill-topic {
    background: #faefe1;
    color: var(--topic);
    border-color: #f6ddc1;
    --icon-color: var(--topic);
  }
  .pill-campaign {
    background: #e1f2f6;
    color: var(--campaign);
    border-color: #c1e4ec;
    --icon-color: var(--campaign);
  }
  .pill-field {
    /* Yellow has very low contrast against white, so the color-mix
       approach used by other variants washes out at any readable mix
       percentage. We use the Tailwind yellow ramp directly for bg
       (yellow-100) / border (yellow-300) / text (yellow-900). The
       icon hue stays anchored to --field so a host page can still
       re-theme the variant by overriding that one token. */
    background: #fef9c3;
    color: #854d0e;
    border-color: #fde68a;
    --icon-color: var(--field);
  }
  .pill-removed {
    /* Removal pill — used when an entity is taken away (e.g. removed
       from a group in the chat history). Fixed at the Tailwind red
       ramp (red-100 bg / red-200 border / red-800 text) for the same
       reason .pill-field is fixed at yellow: color-mixing a light red
       into white washes out before it reads as "red". */
    background: #fee2e2;
    color: #991b1b;
    border-color: #fecaca;
    --icon-color: #991b1b;
  }
  .pill-keyword {
    background: var(--sunken);
    color: var(--text-1);
    border-color: var(--pill-border, var(--border));
    --icon-color: var(--text-2);
    font-family: var(--font-mono);
    font-size: 11.5px;
  }
  .pill-label {
    background: var(--sunken);
    color: var(--text-2);
    border-color: var(--pill-border, var(--border));
    --icon-color: var(--text-2);
  }

  /* Anchor-derived bg/border for browsers with color-mix(). These
     can't be simple same-rule fallbacks: a declaration containing
     var() isn't dropped at parse time, it goes invalid at
     computed-value time and takes the earlier declaration with it. */
  @supports (color: color-mix(in srgb, red, red)) {
    .pill-flow {
      background: color-mix(in srgb, var(--flow) 12%, white);
      border-color: color-mix(in srgb, var(--flow) 25%, white);
    }
    .pill-contact,
    .pill-group {
      background: color-mix(in srgb, var(--recipient) 12%, white);
      border-color: color-mix(in srgb, var(--recipient) 25%, white);
    }
    .pill-channel {
      background: color-mix(in srgb, var(--channel) 12%, white);
      border-color: color-mix(in srgb, var(--channel) 25%, white);
    }
    .pill-topic {
      background: color-mix(in srgb, var(--topic) 12%, white);
      border-color: color-mix(in srgb, var(--topic) 25%, white);
    }
    .pill-campaign {
      background: color-mix(in srgb, var(--campaign) 12%, white);
      border-color: color-mix(in srgb, var(--campaign) 25%, white);
    }
  }
`;
