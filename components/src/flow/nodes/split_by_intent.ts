import { NodeConfig, ACTION_GROUPS, FlowTypes } from '../types';

export const split_by_llm_categorize: NodeConfig = {
  type: 'split_by_intent',
  name: 'Call classifier',
  group: ACTION_GROUPS.services,
  flowTypes: [FlowTypes.VOICE, FlowTypes.MESSAGE, FlowTypes.BACKGROUND]
};
