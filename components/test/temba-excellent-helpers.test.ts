import { expect } from '@open-wc/testing';
import {
  renderCompletionOption,
  getFunctions,
  getCompletions,
  getOffset,
  getVerticalScroll,
  getCompletionName,
  getCompletionSignature
} from '../src/excellent/helpers';
import { CompletionOption, CompletionSchema } from '../src/interfaces';
import { Store } from '../src/store/Store';

describe('excellent/helpers', () => {
  describe('renderCompletionOption', () => {
    it('renders function option when selected', () => {
      const option: CompletionOption = {
        signature: 'sum(values)',
        summary: 'Calculates the sum of values'
      };

      const result = renderCompletionOption(option, true);
      expect(result.strings).to.exist; // It's a TemplateResult
    });

    it('renders function option when not selected', () => {
      const option: CompletionOption = {
        signature: 'sum(values)',
        summary: 'Calculates the sum of values'
      };

      const result = renderCompletionOption(option, false);
      expect(result.strings).to.exist;
    });

    it('renders property option when selected', () => {
      const option: CompletionOption = {
        name: 'first_name',
        summary: 'The contact first name'
      };

      const result = renderCompletionOption(option, true);
      expect(result.strings).to.exist;
    });

    it('renders property option when not selected', () => {
      const option: CompletionOption = {
        name: 'first_name',
        summary: 'The contact first name'
      };

      const result = renderCompletionOption(option, false);
      expect(result.strings).to.exist;
    });

    it('handles function with no summary', () => {
      const option: CompletionOption = {
        signature: 'max(values)',
        summary: ''
      };

      const result = renderCompletionOption(option, true);
      expect(result.strings).to.exist;
    });

    it('handles property with no name', () => {
      const option: CompletionOption = {
        summary: 'Some property'
      };

      const result = renderCompletionOption(option, false);
      expect(result.strings).to.exist;
    });
  });

  describe('getFunctions', () => {
    const functions: CompletionOption[] = [
      { signature: 'sum(values)', summary: 'Sum function' },
      { signature: 'max(values)', summary: 'Max function' },
      { signature: 'min(values)', summary: 'Min function' },
      { name: 'property', summary: 'Not a function' }
    ];

    it('returns all functions when no query provided', () => {
      const result = getFunctions(functions, '');
      expect(result).to.deep.equal(functions);
    });

    it('returns all functions when null query provided', () => {
      const result = getFunctions(functions, null);
      expect(result).to.deep.equal(functions);
    });

    it('filters functions by query prefix', () => {
      const result = getFunctions(functions, 'su');
      expect(result).to.have.length(1);
      expect(result[0].signature).to.equal('sum(values)');
    });

    it('filters functions case-insensitively', () => {
      const result = getFunctions(functions, 'MAX');
      expect(result).to.have.length(1);
      expect(result[0].signature).to.equal('max(values)');
    });

    it('returns empty array when no functions match', () => {
      const result = getFunctions(functions, 'xyz');
      expect(result).to.have.length(0);
    });

    it('ignores non-function options', () => {
      const result = getFunctions(functions, 'prop');
      expect(result).to.have.length(0);
    });

    it('handles empty functions array', () => {
      const result = getFunctions([], 'sum');
      expect(result).to.have.length(0);
    });

    it('handles partial matches', () => {
      const result = getFunctions(functions, 'm');
      expect(result).to.have.length(2); // max and min
    });
  });

  describe('getCompletions', () => {
    const mockSchema: CompletionSchema = {
      types: [
        {
          name: 'contact',
          properties: [
            { key: 'first_name', help: 'First name', type: 'text' },
            { key: 'last_name', help: 'Last name', type: 'text' },
            { key: 'age', help: 'Age', type: 'number' }
          ]
        },
        {
          name: 'fields',
          property_template: {
            key: '{key}',
            help: 'Field {key}',
            type: 'text'
          }
        }
      ],
      root: [
        { key: 'contact', help: 'Contact object', type: 'contact' },
        { key: 'fields', help: 'Contact fields', type: 'fields' }
      ],
      root_no_session: [
        { key: 'contact', help: 'Contact object', type: 'contact' }
      ]
    };

    let mockStore: Store;

    beforeEach(() => {
      mockStore = {
        getCompletions: (type: string) => {
          if (type === 'fields') {
            return ['email', 'phone', 'city'];
          }
          return null;
        }
      } as any;
    });

    it('returns root completions for empty query with session', () => {
      const result = getCompletions(mockSchema, '', true, mockStore);
      expect(result).to.have.length(2);
      expect(result[0].name).to.equal('contact');
      expect(result[1].name).to.equal('fields');
    });

    it('returns root completions for empty query without session', () => {
      const result = getCompletions(mockSchema, '', false, mockStore);
      expect(result).to.have.length(1);
      expect(result[0].name).to.equal('contact');
    });

    it('returns contact properties for contact query', () => {
      const result = getCompletions(mockSchema, 'contact', true, mockStore);
      expect(result).to.have.length(3);
      // Check that the result contains completion options with proper names
      expect(result.map((r) => r.name)).to.include.members([
        'contact.first_name',
        'contact.last_name',
        'contact.age'
      ]);
    });

    it('filters contact properties by partial match', () => {
      const result = getCompletions(
        mockSchema,
        'contact.first',
        true,
        mockStore
      );
      expect(result).to.have.length(1);
      expect(result[0].name).to.equal('contact.first_name');
    });

    it('returns empty array for invalid path', () => {
      const result = getCompletions(
        mockSchema,
        'invalid.path',
        true,
        mockStore
      );
      expect(result).to.have.length(0);
    });

    it('handles template-based types with store completions', () => {
      const result = getCompletions(mockSchema, 'fields', true, mockStore);
      expect(result).to.have.length(3);
      expect(result.map((r) => r.name)).to.include.members([
        'fields.email',
        'fields.phone',
        'fields.city'
      ]);
    });

    it('handles template-based types without store completions', () => {
      const noCompletionsStore = {
        getCompletions: () => null
      } as any;

      const result = getCompletions(
        mockSchema,
        'fields',
        true,
        noCompletionsStore
      );
      expect(result).to.have.length(0);
    });

    it('returns empty array when no schema root', () => {
      const emptySchema: CompletionSchema = {
        types: [],
        root: null,
        root_no_session: null
      };

      const result = getCompletions(emptySchema, '', true, mockStore);
      expect(result).to.have.length(0);
    });

    it('filters root properties by query', () => {
      const result = getCompletions(mockSchema, 'cont', true, mockStore);
      expect(result).to.have.length(1);
      expect(result[0].name).to.equal('contact');
    });

    it('handles nested property access', () => {
      const result = getCompletions(
        mockSchema,
        'contact.last_name',
        true,
        mockStore
      );
      expect(result).to.have.length(1);
      expect(result[0].name).to.equal('contact.last_name');
    });

    it('handles case-insensitive filtering', () => {
      const result = getCompletions(
        mockSchema,
        'contact.FIRST',
        true,
        mockStore
      );
      expect(result).to.have.length(1);
      expect(result[0].name).to.equal('contact.first_name');
    });
  });

  describe('getOffset', () => {
    it('calculates element offset including scroll', () => {
      const element = document.createElement('div');
      element.style.position = 'absolute';
      element.style.top = '100px';
      element.style.left = '50px';
      element.style.width = '200px';
      element.style.height = '150px';
      document.body.appendChild(element);

      const offset = getOffset(element);

      expect(offset).to.have.property('top');
      expect(offset).to.have.property('left');
      expect(typeof offset.top).to.equal('number');
      expect(typeof offset.left).to.equal('number');

      document.body.removeChild(element);
    });

    it('handles elements without explicit positioning', () => {
      const element = document.createElement('span');
      element.textContent = 'test';
      document.body.appendChild(element);

      const offset = getOffset(element);

      expect(offset).to.have.property('top');
      expect(offset).to.have.property('left');

      document.body.removeChild(element);
    });
  });

  describe('getVerticalScroll', () => {
    it('calculates vertical scroll for element', () => {
      const element = document.createElement('div');
      document.body.appendChild(element);

      const scroll = getVerticalScroll(element);

      // Function returns 0 as implemented (seems like stub implementation)
      expect(typeof scroll).to.equal('number');
      expect(scroll).to.equal(0);

      document.body.removeChild(element);
    });

    it('handles element without parent', () => {
      const element = document.createElement('div');

      const scroll = getVerticalScroll(element);
      expect(scroll).to.equal(0);
    });
  });

  describe('getCompletionName', () => {
    it('returns name property when available', () => {
      const option: CompletionOption = {
        name: 'contact_name',
        summary: 'Contact name'
      };

      const name = getCompletionName(option);
      expect(name).to.equal('contact_name');
    });

    it('extracts name from signature when name not available', () => {
      const option: CompletionOption = {
        signature: 'sum(values)',
        summary: 'Sum function'
      };

      const name = getCompletionName(option);
      expect(name).to.equal('sum');
    });

    it('handles complex function signatures', () => {
      const option: CompletionOption = {
        signature: 'format_date(date, format)',
        summary: 'Date formatting function'
      };

      const name = getCompletionName(option);
      expect(name).to.equal('format_date');
    });

    it('handles signature without parentheses gracefully', () => {
      const option: CompletionOption = {
        signature: 'invalid_signature',
        summary: 'Invalid signature'
      };

      const name = getCompletionName(option);
      expect(name).to.equal(''); // indexOf returns -1, substr(0, -1) returns empty string
    });
  });

  describe('getCompletionSignature', () => {
    it('extracts signature parameters', () => {
      const option: CompletionOption = {
        signature: 'sum(values)',
        summary: 'Sum function'
      };

      const signature = getCompletionSignature(option);
      expect(signature).to.equal('(values)');
    });

    it('handles complex parameter signatures', () => {
      const option: CompletionOption = {
        signature: 'format_date(date, format, timezone)',
        summary: 'Date formatting function'
      };

      const signature = getCompletionSignature(option);
      expect(signature).to.equal('(date, format, timezone)');
    });

    it('handles empty parameter signatures', () => {
      const option: CompletionOption = {
        signature: 'now()',
        summary: 'Current date function'
      };

      const signature = getCompletionSignature(option);
      expect(signature).to.equal('()');
    });

    it('handles signature without parentheses', () => {
      const option: CompletionOption = {
        signature: 'invalid',
        summary: 'Invalid signature'
      };

      const signature = getCompletionSignature(option);
      expect(signature).to.equal('d'); // substr from -1 on 'invalid' returns 'd'
    });
  });
});
