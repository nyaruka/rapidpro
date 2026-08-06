import { FlowDefinition } from '../store/flow-definition';
import { ACTION_CONFIG, NODE_CONFIG } from './config';
import { getTranslatableCategoriesForNode } from './categoryLocalization';

export type TranslationType = 'property' | 'category';

export interface TranslationEntry {
  uuid: string;
  type: TranslationType;
  attribute: string;
  from: string;
  to: string | null;
  // Original array form of the source/target. For attributes whose value
  // is an array (e.g. router case `arguments`), these preserve the per-item
  // structure that `from`/`to` would otherwise lose to comma-joining. For
  // scalar attributes the arrays contain a single item.
  fromValues: string[];
  toValues: string[] | null;
}

export interface TranslationBundle {
  nodeUuid: string;
  actionUuid?: string;
  translations: TranslationEntry[];
}

export function formatTranslationValue(value: any): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => formatTranslationValue(entry))
      .filter((entry) => !!entry) as string[];
    return normalized.length > 0 ? normalized.join(', ') : null;
  }

  if (typeof value === 'object') {
    if ('name' in value && value.name) {
      return String(value.name);
    }
    if ('arguments' in value && Array.isArray(value.arguments)) {
      return value.arguments.join(' ');
    }
    return null;
  }

  if (typeof value === 'number') {
    return value.toString();
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  return null;
}

export function findTranslations(
  type: TranslationType,
  uuid: string,
  localizableKeys: string[],
  source: any,
  localization: Record<string, any>
): TranslationEntry[] {
  const translations: TranslationEntry[] = [];

  localizableKeys.forEach((attribute) => {
    if (attribute === 'quick_replies') {
      return;
    }

    const pathSegments = attribute.split('.');
    let from: any = source;
    let to: any = [];

    while (pathSegments.length > 0 && from) {
      if (from.uuid) {
        to = localization[from.uuid];
      }

      const path = pathSegments.shift();
      if (!path) {
        break;
      }

      if (to) {
        to = to[path];
      }
      from = from[path];
    }

    if (!from) {
      return;
    }

    const fromValue = formatTranslationValue(from);
    if (!fromValue) {
      return;
    }

    const toValue = to ? formatTranslationValue(to) : null;

    const toArray = (value: any): string[] => {
      if (Array.isArray(value)) {
        return value.map((v) =>
          v === null || v === undefined ? '' : String(v)
        );
      }
      if (value === null || value === undefined) {
        return [];
      }
      return [String(value)];
    };

    const fromValues = toArray(from);
    const toValues = to !== null && to !== undefined ? toArray(to) : null;

    translations.push({
      uuid,
      type,
      attribute,
      from: fromValue,
      to: toValue,
      fromValues,
      toValues
    });
  });

  return translations;
}

export function buildTranslationBundles(
  definition: FlowDefinition | null | undefined,
  languageCode: string
): TranslationBundle[] {
  if (!definition || !languageCode || languageCode === definition.language) {
    return [];
  }

  const languageLocalization = definition.localization?.[languageCode] || {};
  const bundles: TranslationBundle[] = [];

  definition.nodes.forEach((node) => {
    node.actions?.forEach((action) => {
      const config = ACTION_CONFIG[action.type];
      if (!config?.localizable || config.localizable.length === 0) {
        return;
      }

      // For send_msg actions, only count 'text' for progress tracking
      // (quick_replies and attachments are still localizable but don't count toward progress)
      const localizableKeys =
        action.type === 'send_msg'
          ? config.localizable.filter((key) => key === 'text')
          : config.localizable;

      const translations = findTranslations(
        'property',
        action.uuid,
        localizableKeys,
        action,
        languageLocalization
      );

      if (translations.length > 0) {
        bundles.push({
          nodeUuid: node.uuid,
          actionUuid: action.uuid,
          translations
        });
      }
    });

    const nodeUI = definition._ui?.nodes?.[node.uuid];
    const nodeType = nodeUI?.type;
    if (!nodeType) {
      return;
    }

    if (nodeUI?.config?.localizeRules && node.router?.cases?.length) {
      const ruleTranslations = node.router.cases
        .filter((c) => c.arguments?.length > 0 && c.arguments.some((a) => a))
        .flatMap((c) =>
          findTranslations(
            'property',
            c.uuid,
            ['arguments'],
            c,
            languageLocalization
          )
        );

      if (ruleTranslations.length > 0) {
        bundles.push({
          nodeUuid: node.uuid,
          translations: ruleTranslations
        });
      }
    }

    const nodeConfig = NODE_CONFIG[nodeType];
    if (
      nodeUI?.config?.localizeCategories &&
      nodeConfig?.localizable === 'categories' &&
      node.router?.categories?.length
    ) {
      const translatableCategories = getTranslatableCategoriesForNode(
        nodeType,
        node.router.categories
      );
      const categoryTranslations = translatableCategories.flatMap((category) =>
        findTranslations(
          'category',
          category.uuid,
          ['name'],
          category,
          languageLocalization
        )
      );

      if (categoryTranslations.length > 0) {
        bundles.push({
          nodeUuid: node.uuid,
          translations: categoryTranslations
        });
      }
    }
  });

  return bundles;
}

export function getTranslationCounts(bundles: TranslationBundle[]): {
  total: number;
  localized: number;
} {
  return bundles.reduce(
    (counts, bundle) => {
      bundle.translations.forEach((translation) => {
        counts.total += 1;
        if (translation.to && translation.to.trim().length > 0) {
          counts.localized += 1;
        }
      });
      return counts;
    },
    { total: 0, localized: 0 }
  );
}
