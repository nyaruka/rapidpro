export interface RevisionChanges {
  tags: string[];
}

// "spec" is the housekeeping tag the system attaches when it bumps a flow's
// spec version. It carries no editorial intent, so we strip it at the
// boundary — every downstream consumer (summaries, label caps, no-op
// detection) then operates on a clean tag set without needing special cases.
const NOOP_TAGS = new Set(['spec']);

// Drop tags that don't represent real edits and collapse to null when nothing
// meaningful remains. Returning null lets `isNoOpChanges` and the collapse
// logic treat empty-after-filtering and originally-null the same way.
export function normalizeChanges(
  changes: RevisionChanges | null | undefined
): RevisionChanges | null {
  if (!changes) return null;
  const tags = (changes.tags || []).filter((t) => !NOOP_TAGS.has(t));
  return tags.length === 0 ? null : { tags };
}

const TAG_LABELS: Record<string, { label: string; order: number }> = {
  metadata: { label: 'metadata', order: 0 },
  nodes: { label: 'nodes', order: 1 },
  routing: { label: 'routing', order: 2 },
  actions: { label: 'actions', order: 3 },
  stickies: { label: 'stickies', order: 5 },
  layout: { label: 'layout', order: 6 }
};

function tagToLabel(tag: string): { label: string; order: number } | null {
  if (Object.prototype.hasOwnProperty.call(TAG_LABELS, tag)) {
    return TAG_LABELS[tag];
  }
  if (tag.startsWith('localization:')) {
    return { label: 'translations', order: 4 };
  }
  return null;
}

export function labelsFor(
  changes: RevisionChanges | null | undefined
): Set<string> {
  const result = new Set<string>();
  for (const tag of changes?.tags || []) {
    const entry = tagToLabel(tag);
    if (entry) result.add(entry.label);
  }
  return result;
}

// A revision is a no-op when, after stripping housekeeping tags, nothing
// meaningful is left. These shouldn't break up adjacent edits in the browser.
export function isNoOpChanges(
  changes: RevisionChanges | null | undefined
): boolean {
  return normalizeChanges(changes) === null;
}

export function summarizeChanges(
  changes: RevisionChanges | null | undefined
): string {
  if (!changes) return '';
  const tags = changes.tags || [];
  if (tags.length === 0) return '';

  const orders = new Map<string, number>();
  for (const tag of tags) {
    const entry = tagToLabel(tag);
    if (entry && !orders.has(entry.label)) {
      orders.set(entry.label, entry.order);
    }
  }
  if (orders.size === 0) return '';

  const labels = Array.from(orders.entries())
    .sort((a, b) => a[1] - b[1])
    .map(([label]) => label);

  return `Changed ${joinNaturally(labels)}`;
}

function joinNaturally(parts: string[]): string {
  if (parts.length <= 1) return parts.join('');
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`;
}
