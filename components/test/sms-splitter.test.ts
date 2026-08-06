import { expect } from '@open-wc/testing';
import { splitSMS, GSM, UNICODE } from '../src/display/sms/index';
import { gsmSplit } from '../src/display/sms/gsmsplitter';
import { unicodeSplit } from '../src/display/sms/unicodesplitter';
import {
  validateCharacter,
  validateMessage,
  validateExtendedCharacter
} from '../src/display/sms/gsmvalidator';

// GSM extended characters occupy two septets each
const EXTENDED = ['\f', '^', '{', '}', '\\', '[', '~', ']', '|', '€'];

const repeat = (char: string, count: number) => new Array(count + 1).join(char);

describe('gsmvalidator', () => {
  it('accepts characters in the GSM 03.38 alphabet', () => {
    for (const char of 'abcXYZ019 !?@$#%&*()-+.,/:;<=>') {
      expect(validateCharacter(char), `expected ${char} to be GSM`).to.equal(
        true
      );
    }
  });

  it('accepts the accented and greek characters in the alphabet', () => {
    for (const char of '£¥èéùìòÇØøÅåÆæßÉÄÖÑÜ§¿äöñüàΔΦΓΛΩΠΨΣΘΞ') {
      expect(validateCharacter(char), `expected ${char} to be GSM`).to.equal(
        true
      );
    }
  });

  it('rejects characters outside the alphabet', () => {
    for (const char of '`”…’çÿ✓') {
      expect(
        validateCharacter(char),
        `expected ${char} to be non-GSM`
      ).to.equal(false);
    }
  });

  it('identifies the extended (two septet) characters', () => {
    for (const char of EXTENDED) {
      expect(
        validateExtendedCharacter(char),
        `expected ${char} to be extended`
      ).to.equal(true);
    }
    // ordinary GSM characters are not extended
    expect(validateExtendedCharacter('a')).to.equal(false);
    expect(validateExtendedCharacter('£')).to.equal(false);
  });

  it('validates a whole message only when every character is GSM', () => {
    expect(validateMessage('')).to.equal(true);
    expect(validateMessage('Hello there')).to.equal(true);
    expect(validateMessage('Cost is 5€')).to.equal(true);
    expect(validateMessage('Hello “there”')).to.equal(false);
    expect(validateMessage('Hi 😀')).to.equal(false);
  });
});

describe('gsmSplit', () => {
  it('returns a single empty part for an empty message', () => {
    const result = gsmSplit('', {});
    expect(result.parts).to.have.length(1);
    expect(result.parts[0].content).to.equal('');
    expect(result.parts[0].length).to.equal(0);
    expect(result.parts[0].bytes).to.equal(0);
    expect(result.totalLength).to.equal(0);
    expect(result.totalBytes).to.equal(0);
  });

  it('counts one septet per ordinary character', () => {
    const result = gsmSplit('hello', {});
    expect(result.parts).to.have.length(1);
    expect(result.totalLength).to.equal(5);
    expect(result.totalBytes).to.equal(5);
    expect(result.parts[0].content).to.equal('hello');
  });

  it('counts two septets for each extended character', () => {
    const result = gsmSplit('5€', {});
    expect(result.totalLength).to.equal(2);
    expect(result.totalBytes).to.equal(3);
  });

  it('keeps 160 septets in a single part', () => {
    const result = gsmSplit(repeat('a', 160), {});
    expect(result.parts).to.have.length(1);
    expect(result.totalLength).to.equal(160);
    expect(result.totalBytes).to.equal(160);
  });

  it('splits at 153 septets once the message exceeds a single part', () => {
    const result = gsmSplit(repeat('a', 161), {});
    expect(result.parts).to.have.length(2);
    expect(result.parts[0].bytes).to.equal(153);
    expect(result.parts[0].length).to.equal(153);
    expect(result.parts[1].bytes).to.equal(8);
    expect(result.parts[1].length).to.equal(8);
    expect(result.totalBytes).to.equal(161);
    expect(result.totalLength).to.equal(161);
  });

  it('splits into three parts past two segments', () => {
    const result = gsmSplit(repeat('a', 307), {});
    expect(result.parts).to.have.length(3);
    expect(result.parts.map((p) => p.bytes)).to.deep.equal([153, 153, 1]);
    expect(result.totalBytes).to.equal(307);
  });

  it('never splits an extended character across two parts', () => {
    // 81 euro signs is 162 septets, so it genuinely spans two parts; the
    // boundary falls at 152 rather than 153 so the 77th euro stays whole
    const result = gsmSplit(repeat('€', 81), {});
    expect(result.parts).to.have.length(2);
    expect(result.parts[0].bytes).to.equal(152);
    expect(result.parts[0].length).to.equal(76);
    expect(result.parts[1].bytes).to.equal(10);
    expect(result.parts[1].length).to.equal(5);
    // each part holds only whole characters
    expect(result.parts[0].content).to.equal(repeat('€', 76));
    expect(result.parts[1].content).to.equal(repeat('€', 5));
  });

  it('rejoins a two part split that still fits a single segment', () => {
    // 77 euro signs is 154 septets: banked as two parts internally, but
    // reported as one because it fits inside a single 160 septet message
    const result = gsmSplit(repeat('€', 77), {});
    expect(result.parts).to.have.length(1);
    expect(result.totalBytes).to.equal(154);
    expect(result.totalLength).to.equal(77);
    expect(result.parts[0].content).to.equal(repeat('€', 77));
  });

  it('fits 80 extended characters into a single 160 septet part', () => {
    const result = gsmSplit(repeat('€', 80), {});
    expect(result.parts).to.have.length(1);
    expect(result.totalBytes).to.equal(160);
    expect(result.totalLength).to.equal(80);
  });

  it('replaces non-GSM characters with a space', () => {
    const result = gsmSplit('hi ✓', {});
    expect(result.parts[0].content).to.equal('hi  ');
    expect(result.totalLength).to.equal(4);
    expect(result.totalBytes).to.equal(4);
  });

  it('collapses a surrogate pair into a single replacement space', () => {
    const result = gsmSplit('hi 😀', {});
    // the emoji is two code units but counts once
    expect(result.parts[0].content).to.equal('hi  ');
    expect(result.totalLength).to.equal(4);
  });

  it('omits content when summarizing', () => {
    const result = gsmSplit(repeat('a', 200), { summary: true });
    expect(result.parts).to.have.length(2);
    expect(result.parts[0].content).to.equal(undefined);
    expect(result.parts[1].content).to.equal(undefined);
    // counts are still reported
    expect(result.totalBytes).to.equal(200);
  });
});

describe('unicodeSplit', () => {
  it('returns a single empty part for an empty message', () => {
    const result = unicodeSplit('', {});
    expect(result.parts).to.have.length(1);
    expect(result.parts[0].content).to.equal('');
    expect(result.totalBytes).to.equal(0);
  });

  it('counts two bytes per character', () => {
    const result = unicodeSplit('héllo', {});
    expect(result.totalLength).to.equal(5);
    expect(result.totalBytes).to.equal(10);
  });

  it('keeps 70 characters (140 bytes) in a single part', () => {
    const result = unicodeSplit(repeat('ü', 70), {});
    expect(result.parts).to.have.length(1);
    expect(result.totalLength).to.equal(70);
    expect(result.totalBytes).to.equal(140);
  });

  it('splits at 67 characters once the message exceeds a single part', () => {
    const result = unicodeSplit(repeat('ü', 71), {});
    expect(result.parts).to.have.length(2);
    expect(result.parts[0].bytes).to.equal(134);
    expect(result.parts[0].length).to.equal(67);
    expect(result.parts[1].bytes).to.equal(8);
    expect(result.parts[1].length).to.equal(4);
    expect(result.totalBytes).to.equal(142);
  });

  it('preserves the original text across part boundaries', () => {
    const message = repeat('ü', 71);
    const result = unicodeSplit(message, {});
    expect(result.parts.map((p) => p.content).join('')).to.equal(message);
  });

  it('counts a surrogate pair as one character of four bytes', () => {
    const result = unicodeSplit('😀', {});
    expect(result.parts).to.have.length(1);
    expect(result.totalLength).to.equal(1);
    expect(result.totalBytes).to.equal(4);
  });

  it('never splits a surrogate pair across parts', () => {
    // 36 emoji is 144 bytes, so it genuinely spans two parts; the boundary
    // falls at 132 rather than 134 so the 34th emoji stays whole
    const result = unicodeSplit(repeat('😀', 36), {});
    expect(result.parts).to.have.length(2);
    expect(result.parts[0].bytes).to.equal(132);
    expect(result.parts[0].length).to.equal(33);
    // the trailing part carries whole emoji only
    expect(result.parts[1].content).to.equal(repeat('😀', 3));
    expect(result.parts[1].bytes).to.equal(12);
    expect(result.totalBytes).to.equal(144);
  });

  it('rejoins a two part split that still fits a single segment', () => {
    // 34 emoji is 136 bytes, which fits inside a single 140 byte message
    const result = unicodeSplit(repeat('😀', 34), {});
    expect(result.parts).to.have.length(1);
    expect(result.totalBytes).to.equal(136);
    expect(result.totalLength).to.equal(34);
  });

  it('omits content when summarizing', () => {
    const result = unicodeSplit(repeat('ü', 100), { summary: true });
    expect(result.parts[0].content).to.equal(undefined);
    expect(result.totalBytes).to.equal(200);
  });
});

describe('splitSMS', () => {
  it('detects a GSM message and reports the remaining allowance', () => {
    const result = splitSMS('hello');
    expect(result.characterSet).to.equal(GSM);
    expect(result.parts).to.have.length(1);
    expect(result.length).to.equal(5);
    expect(result.bytes).to.equal(5);
    // a single GSM part holds 160 septets
    expect(result.remainingInPart).to.equal(155);
  });

  it('detects a unicode message', () => {
    const result = splitSMS('hello “there”');
    expect(result.characterSet).to.equal(UNICODE);
    expect(result.length).to.equal(13);
    expect(result.bytes).to.equal(26);
    // a single unicode part holds 70 characters
    expect(result.remainingInPart).to.equal(57);
  });

  it('reports the remaining allowance against the concatenated limit', () => {
    const result = splitSMS(repeat('a', 161));
    expect(result.characterSet).to.equal(GSM);
    expect(result.parts).to.have.length(2);
    // second part has 8 of its 153 septets used
    expect(result.remainingInPart).to.equal(145);
  });

  it('honours a forced GSM character set', () => {
    // “ is not GSM, but forcing GSM encodes it as a space rather than switching
    const result = splitSMS('hello “there”', { characterset: GSM });
    expect(result.characterSet).to.equal(GSM);
    expect(result.bytes).to.equal(13);
  });

  it('honours a forced unicode character set', () => {
    const result = splitSMS('hello', { characterset: UNICODE });
    expect(result.characterSet).to.equal(UNICODE);
    expect(result.bytes).to.equal(10);
  });

  it('treats an emoji message as unicode', () => {
    const result = splitSMS('hi 😀');
    expect(result.characterSet).to.equal(UNICODE);
    expect(result.length).to.equal(4);
    expect(result.bytes).to.equal(10);
  });

  it('handles an empty message', () => {
    const result = splitSMS('');
    expect(result.characterSet).to.equal(GSM);
    expect(result.parts).to.have.length(1);
    expect(result.length).to.equal(0);
    expect(result.remainingInPart).to.equal(160);
  });
});
