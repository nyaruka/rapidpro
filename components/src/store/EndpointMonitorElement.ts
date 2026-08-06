import { PropertyValueMap, PropertyValues } from 'lit';
import { property } from 'lit/decorators.js';
import { CustomEventType } from '../interfaces';

import { StoreMonitorElement } from './StoreMonitorElement';

/**
 * StoreElement is a listener for a given endpoint that re-renders
 * when the underlying store element changes
 */
export class EndpointMonitorElement extends StoreMonitorElement {
  @property({ type: String })
  url: string;

  @property({ type: Boolean })
  showLoading = false;

  @property({ type: Object, attribute: false })
  data: any;

  connectedCallback(): void {
    super.connectedCallback();
    this.prepareData = this.prepareData.bind(this);
  }

  prepareData(data: any): any {
    return data;
  }

  public refresh() {
    this.store.makeRequest(this.url, {
      prepareData: this.prepareData,
      force: true
    });
  }

  protected storeUpdated(event: CustomEvent) {
    if (event.detail.url === this.url) {
      const previous = this.data;
      this.data = event.detail.data;
      this.fireCustomEvent(CustomEventType.Refreshed, {
        data: event.detail.data,
        previous
      });
    }
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    if (changed.has('url') && !this.url) {
      this.data = null;
    }
  }

  protected updated(
    properties: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(properties);
    if (properties.has('url') && this.url) {
      this.store.makeRequest(this.url, { prepareData: this.prepareData });
    }
  }
}
