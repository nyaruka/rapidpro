import { expect } from '@open-wc/testing';
import { getLanguageName } from '../src/languages';

describe('getLanguageName', () => {
  it('returns "Unknown" for the "und" code', () => {
    expect(getLanguageName('und')).to.equal('Unknown');
  });

  it('resolves names via Intl.DisplayNames for known codes', () => {
    expect(getLanguageName('eng')).to.equal('English');
    expect(getLanguageName('fra')).to.equal('French');
    expect(getLanguageName('spa')).to.equal('Spanish');
  });

  it('falls back to the additional lookup map for unsupported codes', () => {
    expect(getLanguageName('prd')).to.equal('Parsi-Dari');
    expect(getLanguageName('pst')).to.equal('Central Pashto');
    expect(getLanguageName('ksw')).to.equal("S'gaw Karen");
    expect(getLanguageName('tdt')).to.equal('Tetun Dili');
  });

  it('returns the raw code for codes not in either source', () => {
    expect(getLanguageName('xx-invalid-code')).to.equal('xx-invalid-code');
  });

  it('returns an empty string for empty or undefined input', () => {
    expect(getLanguageName('')).to.equal('');
    expect(getLanguageName(undefined as unknown as string)).to.equal('');
  });
});
