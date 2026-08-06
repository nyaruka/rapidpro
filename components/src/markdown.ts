import { html } from 'lit';
import { unsafeHTML } from 'lit-html/directives/unsafe-html.js';
import {
  directive,
  Directive,
  Part,
  PartInfo,
  PartType
} from 'lit/directive.js';
import { Remarkable } from 'remarkable';

export const markdown = new Remarkable();

// Base class for markdown rendering directives
abstract class BaseMarkdownDirective extends Directive {
  constructor(partInfo: PartInfo) {
    super(partInfo);
    // When necessary, validate part in constructor using `part.type`
    if (partInfo.type !== PartType.CHILD) {
      throw new Error('markdown directives only support child expressions');
    }
  }

  // Optional: override update to perform any direct DOM manipulation
  update(part: Part, [initialValue]: any) {
    /* Any imperative updates to DOM/parts would go here */
    return this.render(initialValue);
  }

  // Abstract method to be implemented by subclasses
  abstract render(initialValue: string): any;
}

// Class-based directive for block markdown rendering
export class RenderMarkdown extends BaseMarkdownDirective {
  render(initialValue: string) {
    return html`${unsafeHTML(markdown.render(initialValue))}`;
  }
}

// Class-based directive for inline markdown rendering
export class RenderMarkdownInline extends BaseMarkdownDirective {
  render(initialValue: string) {
    return html`${unsafeHTML(markdown.renderInline(initialValue))}`;
  }
}

export const renderMarkdown = directive(RenderMarkdown);
export const renderMarkdownInline = directive(RenderMarkdownInline);
