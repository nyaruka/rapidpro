const UNHYPHENATED_UUID = /^[0-9a-f]{32}$/;

/**
 * Canonicalizes a uuid the way the server does, so a reference embedded in a
 * flow definition in some other form (uppercase, braced, unhyphenated) still
 * matches the normalized uuid the endpoint echoes back.
 *
 * This lives in its own module with no imports so both the store's asset cache
 * and the flow definition rewriter can share it - they sit on opposite sides of
 * a `Store -> AppState -> dependencies` chain, so a shared helper in either one
 * would close an import cycle.
 */
export const normalizeUuid = (uuid: string): string => {
  const trimmed = uuid
    .trim()
    .replace(/^\{|\}$/g, '')
    .toLowerCase();
  if (UNHYPHENATED_UUID.test(trimmed)) {
    return [
      trimmed.slice(0, 8),
      trimmed.slice(8, 12),
      trimmed.slice(12, 16),
      trimmed.slice(16, 20),
      trimmed.slice(20)
    ].join('-');
  }
  return trimmed;
};
