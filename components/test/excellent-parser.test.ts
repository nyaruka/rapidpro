import { expect } from '@open-wc/testing';
import ExcellentParser, { isWordChar } from '../src/excellent/ExcellentParser';

const parser = new ExcellentParser('@', [
  'contact',
  'fields',
  'globals',
  'urns',
  'results',
  'parent',
  'child'
]);

describe('excellent/ExcellentParser', () => {
  describe('isWordChar', () => {
    it('accepts letters, digits and underscore', () => {
      for (const ch of 'azAZ09_') {
        expect(isWordChar(ch), `expected ${ch} to be a word char`).to.equal(
          true
        );
      }
    });

    it('rejects punctuation', () => {
      for (const ch of ' .,()@"-') {
        expect(isWordChar(ch), `expected ${ch} to not be a word char`).to.equal(
          false
        );
      }
    });

    it('treats the numeric end of input sentinel as a word char', () => {
      // findExpressions passes 0 for "past the end of the input", which the
      // '0' <= ch <= '9' comparison coerces numerically and so accepts;
      // callers guard on nextCh === 0 separately rather than relying on this
      expect(isWordChar(0)).to.equal(true);
    });
  });

  describe('expressionContext', () => {
    it('returns null when there are no expressions', () => {
      expect(parser.expressionContext('')).to.equal(null);
      expect(parser.expressionContext('hello there')).to.equal(null);
    });

    it('returns the expression being typed, without its prefix', () => {
      expect(parser.expressionContext('hi @contact')).to.equal('contact');
      expect(parser.expressionContext('hi @contact.na')).to.equal('contact.na');
    });

    it('returns null once an identifier expression has ended', () => {
      // the trailing space terminates the expression, so nothing is being edited
      expect(parser.expressionContext('hi @contact.name ')).to.equal(null);
      expect(parser.expressionContext('hi @contact.name and more')).to.equal(
        null
      );
    });

    it('returns an unbalanced parenthesised expression as still open', () => {
      expect(parser.expressionContext('hi @(1 + ')).to.equal('(1 + ');
      expect(parser.expressionContext('hi @(upper(')).to.equal('(upper(');
    });

    it('returns null once parentheses balance and the expression closes', () => {
      expect(parser.expressionContext('hi @(1 + 2)')).to.equal(null);
    });

    it('tracks only the last expression in the text', () => {
      expect(parser.expressionContext('@contact.name said @globa')).to.equal(
        'globa'
      );
    });

    it('ignores escaped prefixes', () => {
      expect(parser.expressionContext('email me @@ho')).to.equal(null);
    });
  });

  describe('autoCompleteContext', () => {
    it('returns the identifier being completed', () => {
      expect(parser.autoCompleteContext('contact')).to.equal('contact');
      expect(parser.autoCompleteContext('contact.na')).to.equal('contact.na');
    });

    it('returns null inside an open string literal', () => {
      expect(parser.autoCompleteContext('(upper("cont')).to.equal(null);
    });

    it('resumes completion after a string literal closes', () => {
      expect(parser.autoCompleteContext('(upper("abc") & contact')).to.equal(
        'contact'
      );
    });

    it('flags a bare open parenthesis with a leading hash', () => {
      // '#' marks that a function name is being completed rather than a field
      expect(parser.autoCompleteContext('(')).to.equal(null);
      expect(parser.autoCompleteContext('(upper(')).to.equal('#upper');
    });

    it('offers nothing directly after a closed function call', () => {
      // the closing paren rewinds past the whole call, leaving no fragment
      expect(parser.autoCompleteContext('(upper(contact.name)')).to.equal(null);
    });

    it('resumes completion after a closed function call', () => {
      expect(
        parser.autoCompleteContext('(upper(contact.name) & cont')
      ).to.equal('cont');
    });

    it('completes the argument after a comma', () => {
      expect(parser.autoCompleteContext('(split(contact.name, ')).to.equal(
        '#split'
      );
    });

    it('returns null when there is nothing completable', () => {
      expect(parser.autoCompleteContext('')).to.equal(null);
      expect(parser.autoCompleteContext('1 + 2')).to.equal(null);
    });

    it('stops at a non word, non period character', () => {
      expect(parser.autoCompleteContext('1+contact.name')).to.equal(
        'contact.name'
      );
    });
  });

  describe('functionContext', () => {
    it('returns the enclosing function name', () => {
      expect(parser.functionContext('(upper(')).to.equal('upper');
      expect(parser.functionContext('(split(contact.name, ')).to.equal('split');
    });

    it('returns empty when not inside a function call', () => {
      expect(parser.functionContext('')).to.equal('');
      expect(parser.functionContext('contact.name')).to.equal('');
    });

    it('stops at an expression prefix', () => {
      expect(parser.functionContext('@contact')).to.equal('');
    });

    it('ignores parentheses inside string literals', () => {
      expect(parser.functionContext('(upper("a(b", ')).to.equal('upper');
    });
  });

  describe('getContactFields', () => {
    it('returns an empty list when there are no expressions', () => {
      expect(parser.getContactFields('')).to.deep.equal([]);
      expect(parser.getContactFields('just some text')).to.deep.equal([]);
    });

    it('finds a bare fields reference', () => {
      expect(parser.getContactFields('hi @fields.age')).to.deep.equal(['age']);
    });

    it('finds a contact prefixed fields reference', () => {
      expect(parser.getContactFields('hi @contact.fields.age')).to.deep.equal([
        'age'
      ]);
    });

    it('finds fields inside a parenthesised expression', () => {
      expect(
        parser.getContactFields('@(upper(contact.fields.first_name))')
      ).to.deep.equal(['first_name']);
    });

    it('collects several distinct fields', () => {
      const found = parser.getContactFields(
        'hi @contact.fields.age you live in @fields.state'
      );
      expect(found.sort()).to.deep.equal(['age', 'state']);
    });

    it('de-duplicates repeated references to the same field', () => {
      expect(
        parser.getContactFields('@fields.age and again @contact.fields.age')
      ).to.deep.equal(['age']);
    });

    it('handles parent and child scoped fields', () => {
      expect(
        parser.getContactFields('@parent.contact.fields.age')
      ).to.deep.equal(['age']);
    });

    it('ignores non field references', () => {
      expect(
        parser.getContactFields('@contact.name @globals.org')
      ).to.deep.equal([]);
    });
  });

  describe('findExpressions', () => {
    it('returns nothing for text without expressions', () => {
      expect(parser.findExpressions('')).to.have.length(0);
      expect(parser.findExpressions('hello there')).to.have.length(0);
    });

    it('locates a simple identifier expression', () => {
      const found = parser.findExpressions('hi @contact.name there');
      expect(found).to.have.length(1);
      expect(found[0].text).to.equal('@contact.name');
      expect(found[0].start).to.equal(3);
      expect(found[0].end).to.equal(16);
      expect(found[0].closed).to.equal(false);
    });

    it('marks a balanced parenthesised expression as closed', () => {
      const found = parser.findExpressions('@(1 + 2)');
      expect(found).to.have.length(1);
      expect(found[0].text).to.equal('@(1 + 2)');
      expect(found[0].closed).to.equal(true);
    });

    it('does not treat an unbalanced expression as closed', () => {
      const found = parser.findExpressions('@(1 + 2');
      expect(found).to.have.length(1);
      expect(found[0].closed).to.equal(false);
    });

    it('ignores parentheses inside string literals', () => {
      const found = parser.findExpressions('@("a)b")');
      expect(found).to.have.length(1);
      expect(found[0].text).to.equal('@("a)b")');
      expect(found[0].closed).to.equal(true);
    });

    it('skips expressions with a disallowed top level', () => {
      expect(parser.findExpressions('hi @nonsense.foo there')).to.have.length(
        0
      );
    });

    it('allows an incomplete top level at the end of the input', () => {
      // "cont" is a prefix of the allowed "contact" so it is offered while typing
      const found = parser.findExpressions('hi @cont');
      expect(found).to.have.length(1);
      expect(found[0].text).to.equal('@cont');
    });

    it('ignores an escaped prefix', () => {
      expect(parser.findExpressions('email me @@contact')).to.have.length(0);
    });

    it('finds several expressions in one string', () => {
      const found = parser.findExpressions(
        '@contact.name lives in @fields.state'
      );
      expect(found.map((e) => e.text)).to.deep.equal([
        '@contact.name',
        '@fields.state'
      ]);
    });

    it('terminates an identifier at a trailing period', () => {
      const found = parser.findExpressions('call @contact. now');
      expect(found).to.have.length(1);
      expect(found[0].text).to.equal('@contact');
    });
  });
});
