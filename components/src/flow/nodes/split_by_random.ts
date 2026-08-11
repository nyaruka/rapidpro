import { SPLIT_GROUPS, FormData, NodeConfig, FlowTypes } from '../types';
import { Node } from '../../store/flow-definition.d';
import { validateWith } from '../utils';
import { buildCategoriesExitsCases } from './shared';

export const split_by_random: NodeConfig = {
  type: 'split_by_random',
  name: 'Random Split',
  group: SPLIT_GROUPS.split,
  flowTypes: [FlowTypes.VOICE, FlowTypes.MESSAGE, FlowTypes.BACKGROUND],
  form: {
    categories: {
      type: 'array',
      helpText: 'Define the buckets to randomly split contacts into',
      required: true,
      itemLabel: 'Bucket',
      sortable: true,
      minItems: 2,
      maxItems: 10,
      isEmptyItem: (item: any) => {
        return !item.name || item.name.trim() === '';
      },
      itemConfig: {
        name: {
          type: 'text',
          placeholder: 'Bucket name',
          required: true,
          maxLength: 36
        }
      }
    }
  },
  layout: ['categories'],
  validate: validateWith((formData, errors) => {
    if (!formData.categories || !Array.isArray(formData.categories)) return;

    const categories = formData.categories.filter(
      (item: any) => item?.name && item.name.trim() !== ''
    );

    if (categories.length < 2) {
      errors.categories = 'At least 2 buckets are required for random split';
    }

    const duplicateCategories: string[] = [];
    const lowerCaseMap = new Map<string, string[]>();

    categories.forEach((category) => {
      const lowerName = category.name.trim().toLowerCase();
      if (!lowerCaseMap.has(lowerName)) {
        lowerCaseMap.set(lowerName, []);
      }
      lowerCaseMap.get(lowerName).push(category.name.trim());
    });

    lowerCaseMap.forEach((originalNames) => {
      if (originalNames.length > 1) {
        duplicateCategories.push(...originalNames);
      }
    });

    if (duplicateCategories.length > 0) {
      const uniqueDuplicates = [...new Set(duplicateCategories)];
      errors.categories = `Duplicate bucket names found: ${uniqueDuplicates.join(
        ', '
      )}`;
    }
  }),
  toFormData: (node: Node) => {
    // Extract categories from the existing node structure
    const categories =
      node.router?.categories?.map((cat) => ({ name: cat.name })) || [];

    return {
      uuid: node.uuid,
      categories: categories
    };
  },
  fromFormData: (formData: FormData, originalNode: Node): Node => {
    const userCategories = (formData.categories || [])
      .filter((item: any) => item?.name?.trim())
      .map((item: any) => item.name.trim());

    const existingCategories = originalNode.router?.categories || [];
    const existingExits = originalNode.exits || [];

    const { categories, exits } = buildCategoriesExitsCases(
      userCategories.map((name) => ({ name })),
      existingCategories,
      existingExits
    );

    return {
      uuid: originalNode.uuid,
      actions: originalNode.actions || [],
      router: {
        type: 'random',
        categories
      },
      exits
    };
  },
  router: {
    type: 'random'
  },

  // Localization support for categories
  localizable: 'categories'
};
