// Temporary: Legacy support for terminal nodes (nodes with a terminal action
// like enter_flow with terminal: true). This node type and its reclassification
// logic in AppState.ts can be removed once we stop supporting terminal nodes.

import { NodeConfig } from '../types';

export const terminal: NodeConfig = {
  type: 'terminal'
};
