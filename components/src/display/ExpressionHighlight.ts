import { css, html, LitElement, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { tokenize, Token } from '../excellent/tokenizer';
import {
  getTokenClass,
  tokenCss,
  EXPRESSION_TOKENS
} from '../excellent/token-styles';
import { sessionParser } from '../excellent/helpers';

export class ExpressionHighlight extends LitElement {
  static get styles() {
    return [
      tokenCss,
      css`
        :host {
          display: inline;
        }
      `
    ];
  }

  @property({ type: String })
  private text = '';

  private observer: MutationObserver;

  connectedCallback(): void {
    super.connectedCallback();
    this.text = this.textContent || '';
    this.observer = new MutationObserver(() => {
      this.text = this.textContent || '';
    });
    this.observer.observe(this, {
      childList: true,
      characterData: true,
      subtree: true
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.observer?.disconnect();
  }

  private renderTokens(): TemplateResult[] {
    const tokens = tokenize(this.text, sessionParser);
    return tokens.map((token: Token) => {
      const cls = getTokenClass(token);
      const isMono = EXPRESSION_TOKENS.has(token.type);
      const classes = isMono ? `${cls} tok-mono` : cls;
      return html`<span class="${classes}">${token.text}</span>`;
    });
  }

  public render(): TemplateResult {
    return html`${this.renderTokens()}`;
  }
}
