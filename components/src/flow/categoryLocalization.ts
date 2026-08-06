import { Category } from '../store/flow-definition';
import { NODE_CONFIG } from './config';
import { SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION } from './categoryUtils';

export function getTranslatableCategoriesForNode(
  nodeType: string | undefined,
  categories: Category[] | undefined
): Category[] {
  if (!nodeType || !categories?.length) {
    return [];
  }

  const config = NODE_CONFIG[nodeType];
  const blocked = config?.nonTranslatableCategories;

  if (!blocked) {
    return [...categories];
  }

  if (blocked === 'all') {
    return categories.filter((category) =>
      SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION.has(category.name)
    );
  }

  const blockedSet = new Set(blocked);
  return categories.filter(
    (category) =>
      !blockedSet.has(category.name) ||
      SYSTEM_CATEGORIES_ALLOWED_FOR_TRANSLATION.has(category.name)
  );
}

export function hasTranslatableCategoriesForNode(
  nodeType: string | undefined,
  categories: Category[] | undefined
): boolean {
  return getTranslatableCategoriesForNode(nodeType, categories).length > 0;
}
