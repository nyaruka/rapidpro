import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { getClasses } from '../utils';

export class FloatingTab extends RapidElement {
  static get styles() {
    return css`
      .tab.hidden {
        transform: translateX(calc(100% + var(--floating-tab-clip, 0px)));
      }

      .tab.active {
        transform: translateX(calc(100% - 8px));
        clip-path: inset(0 calc(100% - 8px) 0 0);
        pointer-events: none;
      }

      .tab {
        position: fixed;
        right: var(--floating-tab-clip, 0px);
        z-index: 4998;
        display: flex;
        align-items: center;
        padding: 12px;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        cursor: pointer;
        box-shadow: -2px 2px 8px rgba(0, 0, 0, 0.2);
        transition: transform calc(var(--transition-duration, 300ms) * 0.7)
          ease-in-out;
        user-select: none;
      }

      .tab:not(.subdued):hover .icon-container {
        opacity: 1;
      }

      .icon-container {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        opacity: 0.8;
        transition: opacity 0.15s ease-in-out;
      }

      .tab.subdued .icon-container {
        opacity: 0.8;
        transition: opacity 0.15s ease-in-out;
      }

      .tab.subdued:hover .icon-container {
        opacity: 1;
      }

      temba-icon {
        --icon-color: white;
      }

      @keyframes spin {
        0% {
          transform: rotate(0deg);
        }
        100% {
          transform: rotate(360deg);
        }
      }

      .saving .icon-container {
        animation: spin 1s linear infinite;
      }

      .label {
        color: white;
        font-weight: 500;
        font-size: 16px;
        max-width: 0;
        overflow: hidden;
        white-space: nowrap;
        margin-left: 0;
        opacity: 0;
        transition: all var(--transition-duration, 300ms) ease-in-out 1s;
      }

      .tab:not(:hover) .label {
        transition-delay: 0ms;
      }

      .tab:not(.subdued):hover .label {
        max-width: 200px;
        margin-left: 12px;
        opacity: 1;
      }
    `;
  }

  static TAB_HEIGHT = 50;
  static TAB_GAP = 4;
  static START_TOP = 165;
  static allTabs: FloatingTab[] = [];

  @property({ type: String })
  icon: string;

  @property({ type: String })
  label: string;

  @property({ type: String })
  color = '#6B7280';

  @property({ type: Number })
  order = 0;

  @state()
  top = 100;

  @property({ type: Boolean })
  hidden = false;

  @property({ type: Boolean })
  saving = false;

  @property({ type: Boolean })
  active = false;

  connectedCallback() {
    super.connectedCallback();
    FloatingTab.allTabs.push(this);
    FloatingTab.updateAllPositions();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    const index = FloatingTab.allTabs.indexOf(this);
    if (index > -1) {
      FloatingTab.allTabs.splice(index, 1);
    }
    FloatingTab.updateAllPositions();
  }

  public static updateAllPositions() {
    const sorted = [...FloatingTab.allTabs].sort((a, b) => a.order - b.order);
    sorted.forEach((tab, index) => {
      tab.top =
        FloatingTab.START_TOP +
        index * (FloatingTab.TAB_HEIGHT + FloatingTab.TAB_GAP);
    });
  }

  public updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    if (changes.has('hidden')) {
      this.classList.toggle('hidden', this.hidden);
    }
    if (changes.has('active')) {
      // re-render siblings so they pick up the subdued state
      FloatingTab.allTabs.forEach((tab) => {
        if (tab !== this) {
          tab.requestUpdate();
        }
      });
    }
  }

  private handleClick() {
    this.fireCustomEvent(CustomEventType.ButtonClicked, {
      action: 'toggle'
    });
  }

  public static showAllTabs() {
    FloatingTab.allTabs.forEach((tab) => {
      tab.hidden = false;
    });
  }

  public static hideAllTabs() {
    FloatingTab.allTabs.forEach((tab) => {
      tab.hidden = true;
    });
  }

  public render(): TemplateResult {
    const tabStyle = `
      background-color: ${this.color};
      top: ${this.top}px;
    `;

    const anyActive = FloatingTab.allTabs.some((tab) => tab.active);

    const classes = getClasses({
      tab: true,
      hidden: this.hidden,
      saving: this.saving,
      active: this.active,
      subdued: anyActive
    });

    const iconName = this.saving ? 'progress_spinner' : this.icon;

    return html`
      <div class="${classes}" style="${tabStyle}" @click=${this.handleClick}>
        <div class="icon-container">
          ${iconName
            ? html`<temba-icon size="1.5" name="${iconName}"></temba-icon>`
            : ''}
        </div>
        <div class="label">${this.label}</div>
      </div>
    `;
  }
}
