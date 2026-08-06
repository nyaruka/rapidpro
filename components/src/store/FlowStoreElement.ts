import { html, PropertyValueMap, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { FlowDetails } from '../interfaces';
import { EndpointMonitorElement } from './EndpointMonitorElement';

export class FlowStoreElement extends EndpointMonitorElement {
  @property({ type: String })
  flow: string;

  @property({ type: Object, attribute: false })
  data: FlowDetails;

  @property({ type: String })
  endpoint = '/api/v2/flows.json?uuid=';

  prepareData(data: any) {
    if (data && data.length > 0) {
      data = data[0];
    }
    return data;
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    if (changes.has('flow')) {
      if (this.flow) {
        this.url = `${this.endpoint}${this.flow}`;
      } else {
        this.url = null;
      }
    }
  }

  public render(): TemplateResult {
    if (!this.data) {
      return;
    }
    return html`<div></div>`;
  }
}
