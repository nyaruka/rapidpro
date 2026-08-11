import { expect } from '@open-wc/testing';
import {
  RESERVED_CATEGORY_NAMES,
  SYSTEM_CATEGORY_NAMES,
  SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION,
  categoryNamesEqual,
  collectReservedCategoryErrors,
  findCategoryByName,
  findReservedNames,
  isReservedCategoryName,
  isSystemCategory
} from '../../src/flow/categoryUtils';

describe('categoryUtils', () => {
  describe('isReservedCategoryName', () => {
    it('matches the canonical reserved names', () => {
      for (const name of RESERVED_CATEGORY_NAMES) {
        expect(isReservedCategoryName(name)).to.be.true;
      }
    });

    it('is case-insensitive and trims whitespace', () => {
      expect(isReservedCategoryName('OTHER')).to.be.true;
      expect(isReservedCategoryName('other')).to.be.true;
      expect(isReservedCategoryName('  No Response  ')).to.be.true;
      expect(isReservedCategoryName('all responses')).to.be.true;
    });

    it('rejects unrelated names and empties', () => {
      expect(isReservedCategoryName('Yes')).to.be.false;
      expect(isReservedCategoryName('')).to.be.false;
      expect(isReservedCategoryName(undefined as any)).to.be.false;
    });
  });

  describe('isSystemCategory', () => {
    it('matches the canonical system categories', () => {
      for (const name of SYSTEM_CATEGORY_NAMES) {
        expect(isSystemCategory(name)).to.be.true;
      }
    });

    it('is case-insensitive', () => {
      expect(isSystemCategory('other')).to.be.true;
      expect(isSystemCategory('NO RESPONSE')).to.be.true;
    });

    it('treats Failure/Success as non-system (they are reserved but not system-generated for filtering)', () => {
      expect(isSystemCategory('Failure')).to.be.false;
      expect(isSystemCategory('Success')).to.be.false;
    });
  });

  describe('categoryNamesEqual', () => {
    it('compares names case-insensitively with trimming', () => {
      expect(categoryNamesEqual('Other', 'OTHER')).to.be.true;
      expect(categoryNamesEqual('  Other ', 'other')).to.be.true;
      expect(categoryNamesEqual('Yes', 'No')).to.be.false;
    });
  });

  describe('findCategoryByName', () => {
    it('finds categories regardless of casing', () => {
      const categories = [
        { uuid: 'a', name: 'Other' },
        { uuid: 'b', name: 'Yes' }
      ];
      expect(findCategoryByName(categories, 'other')?.uuid).to.equal('a');
      expect(findCategoryByName(categories, '  YES ')?.uuid).to.equal('b');
      expect(findCategoryByName(categories, 'missing')).to.be.undefined;
    });
  });

  describe('findReservedNames', () => {
    it('returns only names that collide with reserved names, preserving casing', () => {
      const names = ['yes', 'Other', 'no response', 'custom'];
      expect(findReservedNames(names)).to.deep.equal(['Other', 'no response']);
    });

    it('de-duplicates collisions that differ only in casing', () => {
      const names = ['Other', 'OTHER', 'other'];
      expect(findReservedNames(names)).to.deep.equal(['Other']);
    });

    it('ignores empty and whitespace-only entries', () => {
      expect(findReservedNames(['', '   ', 'Yes'])).to.deep.equal([]);
    });
  });

  describe('collectReservedCategoryErrors', () => {
    it('flags reserved names in categories[] (split_by_random)', () => {
      const errors = collectReservedCategoryErrors({
        categories: [{ name: 'A' }, { name: 'Other' }]
      });
      expect(errors.categories).to.match(/Reserved category names/);
      expect(errors.categories).to.include('Other');
    });

    it('flags reserved names in groups[] (split_by_groups edge case)', () => {
      const errors = collectReservedCategoryErrors({
        groups: [
          { uuid: 'g1', name: 'Leads' },
          { uuid: 'g2', name: 'no response' }
        ]
      });
      expect(errors.groups).to.match(/Reserved category names/);
      expect(errors.groups).to.include('no response');
    });

    it('flags reserved names in rules[].category (split_by_expression)', () => {
      const errors = collectReservedCategoryErrors({
        rules: [
          { category: 'Yes' },
          { category: 'Failure' },
          { category: 'all responses' }
        ]
      });
      expect(errors.rules).to.match(/Reserved category names/);
      expect(errors.rules).to.include('Failure');
      expect(errors.rules).to.include('all responses');
    });

    it('returns no errors when all names are safe', () => {
      expect(
        collectReservedCategoryErrors({
          categories: [{ name: 'Bucket A' }],
          groups: [{ name: 'Leads' }],
          rules: [{ category: 'Yes' }]
        })
      ).to.deep.equal({});
    });

    it('ignores fields that are not arrays', () => {
      expect(
        collectReservedCategoryErrors({
          categories: 'not an array',
          rules: null
        })
      ).to.deep.equal({});
    });
  });

  describe('SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION', () => {
    it('exposes the allow-list as a Set', () => {
      expect(SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION.has('Other')).to.be.true;
      expect(SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION.has('No Response')).to.be
        .true;
      expect(SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION.has('Failure')).to.be
        .false;
    });
  });
});
