import { Chat } from './src/display/Chat';
import { VectorIcon } from './src/display/Icon';
import { WebChat } from './src/webchat/WebChat';

export function addCustomElement(name: string, comp: any) {
  if (!window.customElements.get(name)) {
    window.customElements.define(name, comp);
  }
}

addCustomElement('temba-icon', VectorIcon);
addCustomElement('temba-chat', Chat);
addCustomElement('temba-webchat', WebChat);
