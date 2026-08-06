import { expect } from '@open-wc/testing';
import { generateDefaultCategoryName } from '../src/utils';
import { getOperatorConfig } from '../src/flow/operators';

/**
 * Tests for default category name generation from rule arguments.
 */
describe('generateDefaultCategoryName', () => {
  describe('word-list operators', () => {
    it('uses only the first word for has_any_word', () => {
      expect(
        generateDefaultCategoryName(
          'has_any_word',
          getOperatorConfig,
          'red maroon fire'
        )
      ).to.equal('Red');
    });

    it('uses only the first word for has_all_words', () => {
      expect(
        generateDefaultCategoryName(
          'has_all_words',
          getOperatorConfig,
          'quick brown fox'
        )
      ).to.equal('Quick');
    });

    it('handles a single word', () => {
      expect(
        generateDefaultCategoryName('has_any_word', getOperatorConfig, 'blue')
      ).to.equal('Blue');
    });

    it('ignores surrounding and repeated whitespace', () => {
      expect(
        generateDefaultCategoryName(
          'has_any_word',
          getOperatorConfig,
          '  green   yellow  '
        )
      ).to.equal('Green');
    });

    it('strips trailing punctuation from a comma-separated list', () => {
      expect(
        generateDefaultCategoryName(
          'has_any_word',
          getOperatorConfig,
          'red, blue, green'
        )
      ).to.equal('Red');
    });

    it('returns empty string for empty argument', () => {
      expect(
        generateDefaultCategoryName('has_any_word', getOperatorConfig, '')
      ).to.equal('');
    });
  });

  describe('phrase operators keep the full value', () => {
    it('capitalizes the whole phrase for has_phrase', () => {
      expect(
        generateDefaultCategoryName(
          'has_phrase',
          getOperatorConfig,
          'thank you'
        )
      ).to.equal('Thank you');
    });

    it('capitalizes the whole phrase for has_only_phrase', () => {
      expect(
        generateDefaultCategoryName(
          'has_only_phrase',
          getOperatorConfig,
          'no thanks'
        )
      ).to.equal('No thanks');
    });

    it('capitalizes the whole phrase for has_beginning', () => {
      expect(
        generateDefaultCategoryName(
          'has_beginning',
          getOperatorConfig,
          'hello there'
        )
      ).to.equal('Hello there');
    });
  });
});
