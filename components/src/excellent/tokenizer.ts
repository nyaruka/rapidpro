import ExcellentParser from './ExcellentParser';

export enum TokenType {
  Text = 'text',
  ExpressionPrefix = 'prefix',
  Identifier = 'identifier',
  Paren = 'paren',
  Operator = 'operator',
  FunctionName = 'fn',
  StringLiteral = 'string',
  NumberLiteral = 'number',
  Keyword = 'keyword',
  ContextRef = 'context-ref',
  Separator = 'separator',
  Whitespace = 'ws',
  Arrow = 'arrow',
  Bracket = 'bracket',
  EscapedAt = 'escaped-at'
}

export interface Token {
  type: TokenType;
  text: string;
  start: number;
  depth?: number;
  balanced?: boolean;
}

const KEYWORDS = new Set(['true', 'false', 'null']);
const SINGLE_OPERATORS = new Set(['+', '-', '*', '/', '^', '&', '=', '<', '>']);
const isDigit = (ch: string): boolean => ch >= '0' && ch <= '9';
const isWordChar = (ch: string): boolean =>
  (ch >= 'a' && ch <= 'z') ||
  (ch >= 'A' && ch <= 'Z') ||
  (ch >= '0' && ch <= '9') ||
  ch === '_';

/**
 * Tokenizes the interior of a parenthesized expression (everything after the opening @().
 * The body string should NOT include the leading @ or the outer parentheses.
 */
function tokenizeExpressionBody(
  body: string,
  baseOffset: number,
  initialDepth: number
): Token[] {
  const tokens: Token[] = [];
  let pos = 0;
  let depth = initialDepth;

  const peek = (offset = 0): string | undefined => body[pos + offset];

  const flushIdentifier = (start: number, end: number): void => {
    const text = body.substring(start, end);
    const absStart = baseOffset + start;

    // check if keyword
    if (KEYWORDS.has(text.toLowerCase())) {
      tokens.push({
        type: TokenType.Keyword,
        text,
        start: absStart
      });
      return;
    }

    // check if followed by ( → function name
    let lookAhead = end;
    while (lookAhead < body.length && body[lookAhead] === ' ') {
      lookAhead++;
    }
    if (lookAhead < body.length && body[lookAhead] === '(') {
      tokens.push({
        type: TokenType.FunctionName,
        text,
        start: absStart
      });
      return;
    }

    // otherwise context reference
    tokens.push({
      type: TokenType.ContextRef,
      text,
      start: absStart
    });
  };

  while (pos < body.length) {
    const ch = body[pos];

    // string literal
    if (ch === '"') {
      const start = pos;
      pos++; // skip opening quote
      while (pos < body.length) {
        if (
          body[pos] === '\\' &&
          pos + 1 < body.length &&
          body[pos + 1] === '"'
        ) {
          pos += 2; // skip escaped quote
        } else if (body[pos] === '"') {
          pos++; // skip closing quote
          break;
        } else {
          pos++;
        }
      }
      tokens.push({
        type: TokenType.StringLiteral,
        text: body.substring(start, pos),
        start: baseOffset + start
      });
      continue;
    }

    // number literal
    if (isDigit(ch) || (ch === '.' && peek(1) && isDigit(peek(1)))) {
      const start = pos;
      while (pos < body.length && isDigit(body[pos])) {
        pos++;
      }
      if (
        pos < body.length &&
        body[pos] === '.' &&
        pos + 1 < body.length &&
        isDigit(body[pos + 1])
      ) {
        pos++; // skip decimal point
        while (pos < body.length && isDigit(body[pos])) {
          pos++;
        }
      }
      tokens.push({
        type: TokenType.NumberLiteral,
        text: body.substring(start, pos),
        start: baseOffset + start
      });
      continue;
    }

    // identifier (word chars and dots)
    if (isWordChar(ch) && !isDigit(ch)) {
      const start = pos;
      while (
        pos < body.length &&
        (isWordChar(body[pos]) || body[pos] === '.')
      ) {
        // don't end on a trailing dot
        if (
          body[pos] === '.' &&
          (pos + 1 >= body.length || !isWordChar(body[pos + 1]))
        ) {
          break;
        }
        pos++;
      }
      flushIdentifier(start, pos);
      continue;
    }

    // parentheses
    if (ch === '(') {
      tokens.push({
        type: TokenType.Paren,
        text: '(',
        start: baseOffset + pos,
        depth,
        balanced: true // will be corrected later if needed
      });
      depth++;
      pos++;
      continue;
    }

    if (ch === ')') {
      depth--;
      tokens.push({
        type: TokenType.Paren,
        text: ')',
        start: baseOffset + pos,
        depth: Math.max(0, depth),
        balanced: true
      });
      pos++;
      continue;
    }

    // brackets
    if (ch === '[' || ch === ']') {
      tokens.push({
        type: TokenType.Bracket,
        text: ch,
        start: baseOffset + pos
      });
      pos++;
      continue;
    }

    // arrow =>
    if (ch === '=' && peek(1) === '>') {
      tokens.push({
        type: TokenType.Arrow,
        text: '=>',
        start: baseOffset + pos
      });
      pos += 2;
      continue;
    }

    // two-char operators: !=, <=, >=
    if (
      (ch === '!' && peek(1) === '=') ||
      (ch === '<' && peek(1) === '=') ||
      (ch === '>' && peek(1) === '=')
    ) {
      tokens.push({
        type: TokenType.Operator,
        text: ch + peek(1),
        start: baseOffset + pos
      });
      pos += 2;
      continue;
    }

    // single-char operators
    if (SINGLE_OPERATORS.has(ch)) {
      tokens.push({
        type: TokenType.Operator,
        text: ch,
        start: baseOffset + pos
      });
      pos++;
      continue;
    }

    // comma separator
    if (ch === ',') {
      tokens.push({
        type: TokenType.Separator,
        text: ',',
        start: baseOffset + pos
      });
      pos++;
      continue;
    }

    // whitespace
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      const start = pos;
      while (
        pos < body.length &&
        (body[pos] === ' ' ||
          body[pos] === '\t' ||
          body[pos] === '\n' ||
          body[pos] === '\r')
      ) {
        pos++;
      }
      tokens.push({
        type: TokenType.Whitespace,
        text: body.substring(start, pos),
        start: baseOffset + start
      });
      continue;
    }

    // unknown character - emit as text
    tokens.push({
      type: TokenType.Text,
      text: ch,
      start: baseOffset + pos
    });
    pos++;
  }

  return tokens;
}

/**
 * Tokenizes text containing Excellent expressions into a stream of typed tokens.
 * Uses ExcellentParser.findExpressions() to find expression boundaries, then
 * tokenizes expression interiors.
 */
export function tokenize(text: string, parser: ExcellentParser): Token[] {
  if (!text) {
    return [];
  }

  const expressions = parser.findExpressions(text);
  const tokens: Token[] = [];
  let lastEnd = 0;

  for (const expr of expressions) {
    // emit plain text before this expression
    if (expr.start > lastEnd) {
      const plainText = text.substring(lastEnd, expr.start);
      // check for escaped @@ in plain text
      let plainPos = 0;
      while (plainPos < plainText.length) {
        const atIdx = plainText.indexOf('@@', plainPos);
        if (atIdx === -1) {
          if (plainPos < plainText.length) {
            tokens.push({
              type: TokenType.Text,
              text: plainText.substring(plainPos),
              start: lastEnd + plainPos
            });
          }
          break;
        }
        // text before @@
        if (atIdx > plainPos) {
          tokens.push({
            type: TokenType.Text,
            text: plainText.substring(plainPos, atIdx),
            start: lastEnd + plainPos
          });
        }
        tokens.push({
          type: TokenType.EscapedAt,
          text: '@@',
          start: lastEnd + atIdx
        });
        plainPos = atIdx + 2;
      }
    }

    // emit expression tokens
    const exprText = expr.text;

    // emit the @ prefix
    tokens.push({
      type: TokenType.ExpressionPrefix,
      text: '@',
      start: expr.start
    });

    if (exprText.length > 1 && exprText[1] === '(') {
      // parenthesized expression: @(...)
      // emit the outer opening paren
      tokens.push({
        type: TokenType.Paren,
        text: '(',
        start: expr.start + 1,
        depth: 0,
        balanced: expr.closed
      });

      // determine if there's a closing paren
      const hasClosingParen =
        expr.closed && exprText[exprText.length - 1] === ')';
      const bodyEnd = hasClosingParen ? exprText.length - 1 : exprText.length;
      const body = exprText.substring(2, bodyEnd);

      if (body.length > 0) {
        const bodyTokens = tokenizeExpressionBody(
          body,
          expr.start + 2,
          1 // depth starts at 1 (inside the outer parens)
        );
        tokens.push(...bodyTokens);
      }

      // emit the outer closing paren if present
      if (hasClosingParen) {
        tokens.push({
          type: TokenType.Paren,
          text: ')',
          start: expr.start + exprText.length - 1,
          depth: 0,
          balanced: true
        });
      }

      // mark unbalanced parens if expression is not closed
      if (!expr.closed) {
        markUnbalancedParens(tokens, expr.start);
      }
    } else {
      // identifier expression: @contact.name
      tokens.push({
        type: TokenType.Identifier,
        text: exprText.substring(1),
        start: expr.start + 1
      });
    }

    lastEnd = expr.end;
  }

  // emit remaining plain text
  if (lastEnd < text.length) {
    const remaining = text.substring(lastEnd);
    let plainPos = 0;
    while (plainPos < remaining.length) {
      const atIdx = remaining.indexOf('@@', plainPos);
      if (atIdx === -1) {
        if (plainPos < remaining.length) {
          tokens.push({
            type: TokenType.Text,
            text: remaining.substring(plainPos),
            start: lastEnd + plainPos
          });
        }
        break;
      }
      if (atIdx > plainPos) {
        tokens.push({
          type: TokenType.Text,
          text: remaining.substring(plainPos, atIdx),
          start: lastEnd + plainPos
        });
      }
      tokens.push({
        type: TokenType.EscapedAt,
        text: '@@',
        start: lastEnd + atIdx
      });
      plainPos = atIdx + 2;
    }
  }

  return tokens;
}

/**
 * Marks paren tokens as unbalanced when the expression is not closed.
 * The outermost opening paren that doesn't have a matching close is marked.
 */
function markUnbalancedParens(tokens: Token[], exprStart: number): void {
  // find all paren tokens belonging to this expression
  for (const token of tokens) {
    if (token.type === TokenType.Paren && token.start >= exprStart) {
      if (token.text === '(' && token.depth === 0) {
        token.balanced = false;
      }
    }
  }
}
