function isHighSurrogate(code) {
  return code >= 0xd800 && code <= 0xdbff;
}

export const unicodeSplit = function (message, options) {
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
  let partStart = 0;

  function bank(partEnd = undefined) {
    const msg = {
      content: options.summary
        ? undefined
        : partEnd
          ? message.substring(partStart, partEnd + 1)
          : message.substring(partStart),
      length: length,
      bytes: bytes
    };
    messages.push(msg);

    partStart = partEnd + 1;

    totalLength += length;
    length = 0;
    totalBytes += bytes;
    bytes = 0;
  }

  for (let i = 0, count = message.length; i < count; i++) {
    const code = message.charCodeAt(i);
    const highSurrogate = isHighSurrogate(code);

    if (highSurrogate) {
      if (bytes === 132) bank(i - 1);
      bytes += 2;
      i++;
    }

    bytes += 2;
    length++;

    if (bytes === 134) bank(i);
  }

  if (bytes > 0) bank();

  if (messages[1] && totalBytes <= 140) {
    return {
      parts: [
        {
          content: options.summary ? undefined : message,
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
