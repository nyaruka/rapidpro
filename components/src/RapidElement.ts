import { LitElement, PropertyValueMap } from 'lit';
import { CustomEventType } from './interfaces';
import { Color, log } from './utils';
import { property } from 'lit/decorators.js';

const showUpdates = (
  ele: HTMLElement,
  changes: Map<PropertyKey, unknown>,
  firstUpdated = false
) => {
  if (ele['DEBUG_UPDATES'] || ele['DEBUG']) {
    if (changes.size > 0) {
      const fromto = {};
      for (const key of changes.keys()) {
        fromto[key] = [changes[key], ele[key]];
      }

      log(ele.tagName, Color.PURPLE, [
        firstUpdated ? '<first-updated>' : '<updated>',
        fromto
      ]);
    }
  }
};

const showEvent = (ele: HTMLElement, type: string, details = undefined) => {
  if (ele['DEBUG_EVENTS'] || ele['DEBUG']) {
    if (details !== undefined) {
      log(ele.tagName, Color.GREEN, [type, details]);
    } else {
      log(ele.tagName, Color.GREEN, [type]);
    }
  }
};

export interface EventHandler {
  event: string;
  method: EventListener;
  isDocument?: boolean;
  isWindow?: boolean;
}

/**
 * Inline handlers compiled from an element's -<event-type> attribute, keyed
 * by their source. Page authors write a finite set of these, so compiling
 * each one once keeps dispatch off the Function constructor entirely.
 */
const inlineHandlers = new Map<string, (event: Event) => any>();

const compileInlineHandler = (source: string): ((event: Event) => any) => {
  let compiled = inlineHandlers.get(source);
  if (!compiled) {
    compiled = new Function(
      'event',
      `
        with(document) {
          with(this) {
            let handler = ${source};
            if(typeof handler === 'function') {
              handler(event);
            }
          }
        }
      `
    ) as (event: Event) => any;
    inlineHandlers.set(source, compiled);
  }
  return compiled;
};

export class RapidElement extends LitElement {
  DEBUG = false;
  DEBUG_UPDATES = false;
  DEBUG_EVENTS = false;

  @property({ type: String })
  service: string;

  private eles: { [selector: string]: HTMLDivElement } = {};

  // teardowns for the listeners we installed, so disconnecting removes the
  // exact functions we added
  private listenerTeardowns: (() => void)[] = [];

  public getEventHandlers(): EventHandler[] {
    return [];
  }

  /**
   * Adds a listener this element owns the teardown for - it is bound to this
   * element and removed automatically when we disconnect. Use this instead of
   * addEventListener for anything on document or window, where a listener
   * that outlives its element keeps the whole element alive.
   */
  public listenTo(
    target: EventTarget,
    event: string,
    method: EventListener,
    options?: AddEventListenerOptions
  ): void {
    const bound = method.bind(this);
    target.addEventListener(event, bound, options);
    this.listenerTeardowns.push(() =>
      target.removeEventListener(event, bound, options)
    );
  }

  connectedCallback() {
    super.connectedCallback();

    for (const handler of this.getEventHandlers()) {
      const target = handler.isDocument
        ? document
        : handler.isWindow
          ? window
          : this;
      this.listenTo(target, handler.event, handler.method);
    }
  }

  disconnectedCallback() {
    this.listenerTeardowns.forEach((teardown) => teardown());
    this.listenerTeardowns = [];
    super.disconnectedCallback();
  }

  protected firstUpdated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changes);
    showUpdates(this, changes, true);
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    showUpdates(this, changes, false);
  }

  public getHeaders() {
    if (!this.service) {
      return {};
    }

    return {
      'X-Temba-Service-Org': this.service
    };
  }

  public fireEvent(type: string): any {
    showEvent(this, type);

    return this.dispatchEvent(
      new Event(type, {
        bubbles: true,
        composed: true
      })
    );
  }

  swallowEvent(event: Event) {
    event.stopPropagation();
    event.preventDefault();
  }

  public fireCustomEvent(type: CustomEventType, detail: any = {}): any {
    showEvent(this, type, detail);

    const event = new CustomEvent(type, {
      detail,
      bubbles: true,
      composed: true
    });

    return this.dispatchEvent(event);
  }

  public dispatchEvent(event: any): any {
    const dispatched = super.dispatchEvent(event);

    // the page can hang a handler off the target for any of our events, as a
    // -<event-type> property or an attribute of the same name
    const ele = event.target;
    if (!ele) {
      return dispatched;
    }

    const eventFire = (ele as any)['-' + event.type];
    if (eventFire) {
      return eventFire(event);
    }

    const inline = ele.getAttribute ? ele.getAttribute('-' + event.type) : null;
    if (!inline) {
      return dispatched;
    }

    // the compiled handler has no return value of its own, so handing its
    // undefined back would read as a cancelled event - what the caller wants
    // to know is whether anything called preventDefault
    compileInlineHandler(inline).call(ele, event);
    return dispatched;
  }

  public closestElement(selector: string, base: Element = this) {
    function __closestFrom(el: Element | Window | Document): Element {
      if (!el || el === document || el === window) return null;
      if ((el as any).assignedSlot) el = (el as any).assignedSlot;
      const found = (el as Element).closest(selector);
      return found
        ? found
        : __closestFrom(((el as Element).getRootNode() as ShadowRoot).host);
    }
    return __closestFrom(base);
  }

  public getDiv(selector: string) {
    let ele = this.eles[selector];
    if (ele) {
      return ele;
    }

    ele = this.shadowRoot.querySelector(selector);
    if (ele) {
      this.eles[selector] = ele;
    }
    return ele;
  }

  public stopEvent(event: Event) {
    if (event) {
      event.stopPropagation();
      event.preventDefault();
    }
  }

  public isMobile() {
    const win = window as any;
    if (win.isMobile) {
      return win.isMobile();
    }
    return false;
  }
}
