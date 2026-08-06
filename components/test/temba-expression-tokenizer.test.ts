import { expect } from '@open-wc/testing';
import { tokenize, TokenType } from '../src/excellent/tokenizer';
import ExcellentParser from '../src/excellent/ExcellentParser';

const messageParser = new ExcellentParser('@', [
  'contact',
  'fields',
  'globals',
  'urns'
]);

const sessionParser = new ExcellentParser('@', [
  'contact',
  'fields',
  'globals',
  'locals',
  'urns',
  'results',
  'input',
  'run',
  'child',
  'parent',
  'node',
  'webhook',
  'ticket',
  'trigger',
  'resume'
]);

describe('excellent/tokenizer', () => {
  describe('plain text', () => {
    it('returns empty array for empty string', () => {
      const tokens = tokenize('', messageParser);
      expect(tokens).to.have.length(0);
    });

    it('returns single text token for plain text', () => {
      const tokens = tokenize('Hello world', messageParser);
      expect(tokens).to.have.length(1);
      expect(tokens[0].type).to.equal(TokenType.Text);
      expect(tokens[0].text).to.equal('Hello world');
      expect(tokens[0].start).to.equal(0);
    });

    it('returns null/undefined for null input', () => {
      const tokens = tokenize(null, messageParser);
      expect(tokens).to.have.length(0);
    });
  });

  describe('identifier expressions', () => {
    it('tokenizes @contact.name', () => {
      const tokens = tokenize('@contact.name', messageParser);
      expect(tokens).to.have.length(2);
      expect(tokens[0].type).to.equal(TokenType.ExpressionPrefix);
      expect(tokens[0].text).to.equal('@');
      expect(tokens[1].type).to.equal(TokenType.Identifier);
      expect(tokens[1].text).to.equal('contact.name');
    });

    it('tokenizes identifier with surrounding text', () => {
      const tokens = tokenize('Hello @contact.name!', messageParser);
      expect(tokens).to.have.length(4);
      expect(tokens[0].type).to.equal(TokenType.Text);
      expect(tokens[0].text).to.equal('Hello ');
      expect(tokens[1].type).to.equal(TokenType.ExpressionPrefix);
      expect(tokens[2].type).to.equal(TokenType.Identifier);
      expect(tokens[2].text).to.equal('contact.name');
      expect(tokens[3].type).to.equal(TokenType.Text);
      expect(tokens[3].text).to.equal('!');
    });

    it('tokenizes multiple identifier expressions', () => {
      const tokens = tokenize(
        '@contact.first_name @contact.last_name',
        messageParser
      );
      // @contact.first_name = prefix + identifier
      // " " = text
      // @contact.last_name = prefix + identifier
      expect(tokens).to.have.length(5);
      expect(tokens[0].type).to.equal(TokenType.ExpressionPrefix);
      expect(tokens[1].type).to.equal(TokenType.Identifier);
      expect(tokens[1].text).to.equal('contact.first_name');
      expect(tokens[2].type).to.equal(TokenType.Text);
      expect(tokens[2].text).to.equal(' ');
      expect(tokens[3].type).to.equal(TokenType.ExpressionPrefix);
      expect(tokens[4].type).to.equal(TokenType.Identifier);
      expect(tokens[4].text).to.equal('contact.last_name');
    });
  });

  describe('parenthesized expressions', () => {
    it('tokenizes @(1 + 2)', () => {
      const tokens = tokenize('@(1 + 2)', messageParser);
      expect(tokens.length).to.be.greaterThan(0);

      // @ prefix
      expect(tokens[0].type).to.equal(TokenType.ExpressionPrefix);

      // opening paren at depth 0
      expect(tokens[1].type).to.equal(TokenType.Paren);
      expect(tokens[1].text).to.equal('(');
      expect(tokens[1].depth).to.equal(0);
      expect(tokens[1].balanced).to.equal(true);

      // find the number, operator, number
      const numTokens = tokens.filter(
        (t) => t.type === TokenType.NumberLiteral
      );
      expect(numTokens).to.have.length(2);
      expect(numTokens[0].text).to.equal('1');
      expect(numTokens[1].text).to.equal('2');

      const opTokens = tokens.filter((t) => t.type === TokenType.Operator);
      expect(opTokens).to.have.length(1);
      expect(opTokens[0].text).to.equal('+');

      // closing paren
      const lastToken = tokens[tokens.length - 1];
      expect(lastToken.type).to.equal(TokenType.Paren);
      expect(lastToken.text).to.equal(')');
      expect(lastToken.depth).to.equal(0);
    });

    it('tokenizes function call @(upper(contact.name))', () => {
      const tokens = tokenize('@(upper(contact.name))', sessionParser);

      const fnTokens = tokens.filter((t) => t.type === TokenType.FunctionName);
      expect(fnTokens).to.have.length(1);
      expect(fnTokens[0].text).to.equal('upper');

      const ctxTokens = tokens.filter((t) => t.type === TokenType.ContextRef);
      expect(ctxTokens).to.have.length(1);
      expect(ctxTokens[0].text).to.equal('contact.name');
    });

    it('tokenizes string literal @("hello")', () => {
      const tokens = tokenize('@("hello")', messageParser);

      const strTokens = tokens.filter(
        (t) => t.type === TokenType.StringLiteral
      );
      expect(strTokens).to.have.length(1);
      expect(strTokens[0].text).to.equal('"hello"');
    });

    it('tokenizes number literal @(42)', () => {
      const tokens = tokenize('@(42)', messageParser);

      const numTokens = tokens.filter(
        (t) => t.type === TokenType.NumberLiteral
      );
      expect(numTokens).to.have.length(1);
      expect(numTokens[0].text).to.equal('42');
    });

    it('tokenizes decimal number @(3.14)', () => {
      const tokens = tokenize('@(3.14)', messageParser);

      const numTokens = tokens.filter(
        (t) => t.type === TokenType.NumberLiteral
      );
      expect(numTokens).to.have.length(1);
      expect(numTokens[0].text).to.equal('3.14');
    });

    it('tokenizes keywords @(true)', () => {
      const tokens = tokenize('@(true)', messageParser);

      const kwTokens = tokens.filter((t) => t.type === TokenType.Keyword);
      expect(kwTokens).to.have.length(1);
      expect(kwTokens[0].text).to.equal('true');
    });

    it('tokenizes false keyword', () => {
      const tokens = tokenize('@(false)', messageParser);

      const kwTokens = tokens.filter((t) => t.type === TokenType.Keyword);
      expect(kwTokens).to.have.length(1);
      expect(kwTokens[0].text).to.equal('false');
    });

    it('tokenizes null keyword', () => {
      const tokens = tokenize('@(null)', messageParser);

      const kwTokens = tokens.filter((t) => t.type === TokenType.Keyword);
      expect(kwTokens).to.have.length(1);
      expect(kwTokens[0].text).to.equal('null');
    });

    it('tokenizes all operators', () => {
      const tokens = tokenize('@(1 + 2 - 3 * 4 / 5)', messageParser);

      const opTokens = tokens.filter((t) => t.type === TokenType.Operator);
      expect(opTokens.map((t) => t.text)).to.include.members([
        '+',
        '-',
        '*',
        '/'
      ]);
    });

    it('tokenizes comparison operators', () => {
      const tokens = tokenize('@(1 != 2)', messageParser);
      const opTokens = tokens.filter((t) => t.type === TokenType.Operator);
      expect(opTokens.map((t) => t.text)).to.include('!=');
    });

    it('tokenizes <= and >= operators', () => {
      const tokens = tokenize('@(1 <= 2)', messageParser);
      const opTokens = tokens.filter((t) => t.type === TokenType.Operator);
      expect(opTokens.map((t) => t.text)).to.include('<=');
    });

    it('tokenizes comma separator', () => {
      const tokens = tokenize('@(format(a, b))', messageParser);

      const sepTokens = tokens.filter((t) => t.type === TokenType.Separator);
      expect(sepTokens).to.have.length(1);
      expect(sepTokens[0].text).to.equal(',');
    });

    it('tokenizes brackets', () => {
      const tokens = tokenize('@(items[0])', messageParser);

      const bracketTokens = tokens.filter((t) => t.type === TokenType.Bracket);
      expect(bracketTokens).to.have.length(2);
      expect(bracketTokens[0].text).to.equal('[');
      expect(bracketTokens[1].text).to.equal(']');
    });

    it('tokenizes arrow =>', () => {
      const tokens = tokenize('@((x) => x + 1)', messageParser);

      const arrowTokens = tokens.filter((t) => t.type === TokenType.Arrow);
      expect(arrowTokens).to.have.length(1);
      expect(arrowTokens[0].text).to.equal('=>');
    });
  });

  describe('parenthesis depth tracking', () => {
    it('assigns depth 0 to outermost parens', () => {
      const tokens = tokenize('@(1 + 2)', messageParser);

      const parenTokens = tokens.filter((t) => t.type === TokenType.Paren);
      expect(parenTokens[0].depth).to.equal(0); // (
      expect(parenTokens[1].depth).to.equal(0); // )
    });

    it('assigns increasing depth for nested parens', () => {
      const tokens = tokenize('@(upper(lower(text)))', sessionParser);

      const parenTokens = tokens.filter((t) => t.type === TokenType.Paren);
      // outer ( = depth 0
      // upper( = depth 1
      // lower( = depth 2
      // ) closing lower = depth 2
      // ) closing upper = depth 1
      // ) closing outer = depth 0
      expect(parenTokens[0].depth).to.equal(0);

      // Find the inner parens by checking depths
      const depths = parenTokens.map((t) => t.depth);
      expect(depths).to.include(1);
      expect(depths).to.include(2);
    });

    it('marks all parens as balanced in closed expression', () => {
      const tokens = tokenize('@(upper(text))', sessionParser);

      const parenTokens = tokens.filter((t) => t.type === TokenType.Paren);
      for (const paren of parenTokens) {
        expect(paren.balanced).to.not.equal(false);
      }
    });
  });

  describe('unbalanced parentheses', () => {
    it('marks outer paren as unbalanced in unclosed expression', () => {
      const tokens = tokenize('@(upper(text)', sessionParser);

      const parenTokens = tokens.filter((t) => t.type === TokenType.Paren);
      // The outermost ( should be unbalanced
      const outerParen = parenTokens.find(
        (t) => t.text === '(' && t.depth === 0
      );
      expect(outerParen).to.exist;
      expect(outerParen.balanced).to.equal(false);
    });
  });

  describe('escaped @@', () => {
    it('treats @@ as escaped at sign', () => {
      const tokens = tokenize('Send to user@@example.com', messageParser);

      // Should have text tokens (the @@ may appear as part of plain text
      // depending on parser behavior)
      expect(tokens.length).to.be.greaterThan(0);
      // The full text should be reconstructable from tokens
      const reconstructed = tokens.map((t) => t.text).join('');
      expect(reconstructed).to.equal('Send to user@@example.com');
    });
  });

  describe('mixed content', () => {
    it('handles text with multiple expression types', () => {
      const tokens = tokenize(
        'Hi @contact.name, you scored @(results.score + 10)',
        sessionParser
      );

      const prefixTokens = tokens.filter(
        (t) => t.type === TokenType.ExpressionPrefix
      );
      expect(prefixTokens).to.have.length(2);

      const idTokens = tokens.filter((t) => t.type === TokenType.Identifier);
      expect(idTokens).to.have.length(1);
      expect(idTokens[0].text).to.equal('contact.name');

      const ctxTokens = tokens.filter((t) => t.type === TokenType.ContextRef);
      expect(ctxTokens.length).to.be.greaterThan(0);
    });

    it('preserves text between expressions', () => {
      const input = 'Hello @contact.name, welcome!';
      const tokens = tokenize(input, messageParser);

      const reconstructed = tokens.map((t) => t.text).join('');
      expect(reconstructed).to.equal(input);
    });

    it('reconstructs original text from tokens', () => {
      const inputs = [
        'plain text',
        '@contact.name',
        '@(1 + 2)',
        'Hi @contact.name!',
        '@(upper(contact.name))',
        '@(format(contact.name, "Hello"))',
        'Score: @(results.score + 10) points'
      ];

      for (const input of inputs) {
        const tokens = tokenize(input, sessionParser);
        const reconstructed = tokens.map((t) => t.text).join('');
        expect(reconstructed).to.equal(input);
      }
    });
  });

  describe('session vs message parser', () => {
    it('recognizes session-only contexts with session parser', () => {
      const tokens = tokenize('@results.score', sessionParser);
      expect(tokens).to.have.length(2);
      expect(tokens[0].type).to.equal(TokenType.ExpressionPrefix);
      expect(tokens[1].type).to.equal(TokenType.Identifier);
    });

    it('does not recognize session contexts with message parser', () => {
      const tokens = tokenize('@results.score', messageParser);
      // message parser doesn't include 'results' as allowed top level
      // so the whole thing becomes plain text
      expect(tokens).to.have.length(1);
      expect(tokens[0].type).to.equal(TokenType.Text);
    });
  });

  describe('whitespace in expressions', () => {
    it('preserves whitespace tokens inside expressions', () => {
      const tokens = tokenize('@(1 + 2)', messageParser);

      const wsTokens = tokens.filter((t) => t.type === TokenType.Whitespace);
      expect(wsTokens.length).to.be.greaterThan(0);
    });
  });

  describe('complex expressions', () => {
    it('tokenizes concatenation with &', () => {
      const tokens = tokenize(
        '@(contact.first_name & " " & contact.last_name)',
        sessionParser
      );

      const opTokens = tokens.filter((t) => t.type === TokenType.Operator);
      const ampersands = opTokens.filter((t) => t.text === '&');
      expect(ampersands).to.have.length(2);
    });

    it('tokenizes nested function calls', () => {
      const tokens = tokenize('@(lower(upper(contact.name)))', sessionParser);

      const fnTokens = tokens.filter((t) => t.type === TokenType.FunctionName);
      expect(fnTokens).to.have.length(2);
      expect(fnTokens.map((t) => t.text)).to.include.members([
        'lower',
        'upper'
      ]);
    });
  });
});
