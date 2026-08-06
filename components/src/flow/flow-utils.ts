import { zustand } from '../store/AppState';

/**
 * Excludes flows that are incompatible with the current flow type.
 * Background flows cannot enter message flows.
 */
export function shouldExcludeFlow(flow: any): boolean {
  const definition = zustand.getState().flowDefinition;
  if (!definition) return false;

  // Background flows should not be able to enter message flows
  if (definition.type === 'messaging_background' && flow.type === 'message') {
    return true;
  }

  return false;
}

export type LLMRole = 'engine' | 'editing';

export interface LLMModel {
  uuid: string;
  name: string;
  type?: string;
  description?: string;
  roles?: LLMRole[];
}

export function hasLLMRole(
  model: { roles?: string[] } | null | undefined,
  role: LLMRole
): boolean {
  return model?.roles?.includes(role) ?? false;
}
