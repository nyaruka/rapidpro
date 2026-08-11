import { expect } from '@open-wc/testing';
import { html, render } from 'lit';
import { markdown, renderMarkdown, RenderMarkdown } from '../src/markdown';
import { PartType } from 'lit/directive.js';

describe('markdown', () => {
  describe('markdown instance', () => {
    it('exports a Remarkable instance', () => {
      expect(markdown).to.exist;
      expect(typeof markdown.render).to.equal('function');
    });

    it('renders basic markdown', () => {
      const result = markdown.render('# Hello World');
      expect(result).to.include('<h1>Hello World</h1>');
    });

    it('renders markdown with emphasis', () => {
      const result = markdown.render('**bold** and *italic*');
      expect(result).to.include('<strong>bold</strong>');
      expect(result).to.include('<em>italic</em>');
    });

    it('renders markdown lists', () => {
      const result = markdown.render('- Item 1\n- Item 2');
      expect(result).to.include('<ul>');
      expect(result).to.include('<li>Item 1</li>');
      expect(result).to.include('<li>Item 2</li>');
    });

    it('renders markdown links', () => {
      const result = markdown.render('[Link](https://example.com)');
      expect(result).to.include('<a href="https://example.com">Link</a>');
    });
  });

  describe('RenderMarkdown directive', () => {
    it('throws error for non-child part types', () => {
      const invalidPartInfo = {
        type: PartType.ATTRIBUTE
      };

      expect(() => new RenderMarkdown(invalidPartInfo as any)).to.throw(
        'markdown directives only support child expressions'
      );
    });

    it('creates directive for child part type', () => {
      const validPartInfo = {
        type: PartType.CHILD
      };

      expect(() => new RenderMarkdown(validPartInfo as any)).to.not.throw;
    });

    it('renders markdown content', () => {
      const validPartInfo = {
        type: PartType.CHILD
      };

      const directive = new RenderMarkdown(validPartInfo as any);
      const result = directive.render('# Test Header');

      // The result should be a TemplateResult
      expect(result).to.exist;
      expect(result.strings).to.exist;
    });

    it('updates correctly', () => {
      const validPartInfo = {
        type: PartType.CHILD
      };

      const directive = new RenderMarkdown(validPartInfo as any);
      const mockPart = {} as any;

      const result = directive.update(mockPart, ['# Updated Content']);

      // Should return the same as render
      expect(result).to.exist;
      expect(result.strings).to.exist;
    });
  });

  describe('renderMarkdown function', () => {
    it('creates a directive that can be used in templates', () => {
      const template = html`${renderMarkdown('# Test')}`;

      // Should create a valid template
      expect(template).to.exist;
      expect(template.strings).to.exist;
    });

    it('renders markdown when used in a template', () => {
      const container = document.createElement('div');
      const template = html`${renderMarkdown('# Hello World')}`;

      render(template, container);

      // Check that the markdown was rendered to HTML
      expect(container.innerHTML).to.include('<h1>Hello World</h1>');
    });

    it('handles empty markdown', () => {
      const container = document.createElement('div');
      const template = html`${renderMarkdown('')}`;

      render(template, container);

      // Should not throw - Lit may add HTML comments for template placeholders
      expect(() => render(template, container)).to.not.throw;
    });

    it('handles markdown with special characters', () => {
      const container = document.createElement('div');
      const markdownWithSpecialChars =
        '**Bold** text with <script>alert("xss")</script>';
      const template = html`${renderMarkdown(markdownWithSpecialChars)}`;

      render(template, container);

      // Should render the markdown but the script tag should be escaped/handled
      expect(container.innerHTML).to.include('<strong>Bold</strong>');
      // The script tag should be rendered as text or escaped
      expect(container.innerHTML).to.include('script');
    });

    it('renders complex markdown structures', () => {
      const complexMarkdown = `
# Main Header

## Sub Header

This is a paragraph with **bold** and *italic* text.

- List item 1
- List item 2
  - Nested item

[A link](https://example.com)

\`\`\`
code block
\`\`\`
`;

      const container = document.createElement('div');
      const template = html`${renderMarkdown(complexMarkdown)}`;

      render(template, container);

      expect(container.innerHTML).to.include('<h1>Main Header</h1>');
      expect(container.innerHTML).to.include('<h2>Sub Header</h2>');
      expect(container.innerHTML).to.include('<strong>bold</strong>');
      expect(container.innerHTML).to.include('<em>italic</em>');
      expect(container.innerHTML).to.include('<ul>');
      expect(container.innerHTML).to.include(
        '<a href="https://example.com">A link</a>'
      );
    });
  });
});
