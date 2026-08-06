import { PropertyValueMap } from 'lit';
import { property } from 'lit/decorators.js';
import { CustomEventType } from './interfaces';
import { RapidElement } from './RapidElement';
import { Store } from './store/Store';

export class RefreshElement extends RapidElement {
  @property({ type: String })
  endpoint: string;

  protected updated(
    properties: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    if (properties.has('endpoint')) {
      this.refresh();
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  protected refreshComplete(results: any) {
    // noop
  }

  public refresh(force = false) {
    const store = document.querySelector('temba-store') as Store;
    if (store) {
      store.getResults(this.endpoint, { force }).then((results: any[]) => {
        this.fireCustomEvent(CustomEventType.Refreshed, results);
        this.refreshComplete(results);
      });
    }
  }
}
