import { validateCharacter, validateExtendedCharacter } from './gsmvalidator';

function isHighSurrogate(code) {
  return code >= 0xd800 && code <= 0xdbff;
}

export const gsmSplit = function (message, options) {
  options = options || { summary: false };

  if (message === '') {
    return {
      parts: [
        {
          content: options.summary ? undefined : '',
          length: 0,
          bytes: 0
        }
      ],
      totalLength: 0,
      totalBytes: 0
    };
  }

  const messages = [];
  let length = 0;
  let bytes = 0;
  let totalBytes = 0;
  let totalLength = 0;
  let messagePart = '';

  function bank() {
    const msg = {
      content: options.summary ? undefined : messagePart,
      length: length,
      bytes: bytes
    };
    messages.push(msg);

    totalLength += length;
    length = 0;
    totalBytes += bytes;
    bytes = 0;
    messagePart = '';
  }

  for (let i = 0, count = message.length; i < count; i++) {
    let c = message.charAt(i);

    if (!validateCharacter(c)) {
      if (isHighSurrogate(c.charCodeAt(0))) {
        i++;
      }
      c = '\u0020';
    } else if (validateExtendedCharacter(c)) {
      if (bytes === 152) bank();
      bytes++;
    }

    bytes++;
    length++;

    if (!options.summary) messagePart += c;

    if (bytes === 153) bank();
  }

  if (bytes > 0) bank();

  if (messages[1] && totalBytes <= 160) {
    return {
      parts: [
        {
          content: options.summary
            ? undefined
            : messages[0].content + messages[1].content,
          length: totalLength,
          bytes: totalBytes
        }
      ],
      totalLength: totalLength,
      totalBytes: totalBytes
    };
  }

  return {
    parts: messages,
    totalLength: totalLength,
    totalBytes: totalBytes
  };
};
