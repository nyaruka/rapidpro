import { RapidElement } from './RapidElement';
import { throttle } from './utils';

export class ResizeElement extends RapidElement {
  public handleResize() {
    this.requestUpdate();
  }

  public getEventHandlers() {
    return [
      {
        event: 'resize',
        method: throttle(this.handleResize, 50),
        isWindow: true
      }
    ];
  }
}
