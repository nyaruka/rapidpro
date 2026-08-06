import { html, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { CustomEventType } from '../interfaces';
import { RapidElement } from '../RapidElement';
import { Store } from './Store';

/**
 * StoreMonitorElement notifies when the store is updated and with what url
 */
export class StoreMonitorElement extends RapidElement {
  @property({ type: String })
  url: string;

  @property({ type: Boolean })
  showLoading = false;

  @property({ type: Boolean })
  dirty = false;

  @property({ type: String })
  dirtyMessage: string;

  store: Store;

  markDirty() {
    this.dirty = true;
    this.store.markDirty(this);
    this.fireCustomEvent(CustomEventType.DetailsChanged, {
      dirty: true
    });
  }

  markClean() {
    this.dirty = false;
    this.store.markClean(this);
    this.fireCustomEvent(CustomEventType.DetailsChanged, {
      dirty: false
    });
  }

  private handleStoreUpdated(event: CustomEvent) {
    this.storeUpdated(event);
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/no-empty-function
  protected storeUpdated(event: CustomEvent) {}

  connectedCallback(): void {
    super.connectedCallback();
    this.store = document.querySelector('temba-store') as Store;
    this.handleStoreUpdated = this.handleStoreUpdated.bind(this);
    if (this.store) {
      this.store.addEventListener(
        CustomEventType.StoreUpdated,
        this.handleStoreUpdated
      );
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.store) {
      this.store.removeEventListener(
        CustomEventType.StoreUpdated,
        this.handleStoreUpdated
      );

      this.store.markClean(this);
    }
  }

  public render(): TemplateResult {
    if (!this.store.ready && this.showLoading) {
      return html`<temba-loading></temba-loading>`;
    }
  }
}
