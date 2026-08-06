// Re-export all types and utilities
export * from './types';
import type { ActionConfig, NodeConfig } from './types';

// Import all action configurations
import { add_input_labels } from './actions/add_input_labels';
import { add_contact_urn } from './actions/add_contact_urn';
import { set_contact_field } from './actions/set_contact_field';
import { set_contact_channel } from './actions/set_contact_channel';
import { set_contact_language } from './actions/set_contact_language';
import { set_contact_status } from './actions/set_contact_status';
import { send_broadcast } from './actions/send_broadcast';
import { set_run_result } from './actions/set_run_result';
import { send_msg } from './actions/send_msg';
import { send_email } from './actions/send_email';
import { start_session } from './actions/start_session';
import { set_contact_name } from './actions/set_contact_name';
import { add_contact_groups } from './actions/add_contact_groups';
import { remove_contact_groups } from './actions/remove_contact_groups';
import { request_optin } from './actions/request_optin';
import { say_msg } from './actions/say_msg';
import { play_audio } from './actions/play_audio';
import { enter_flow } from './actions/enter_flow';

// Import all node configurations
import { execute_actions } from './nodes/execute_actions';
import { split_by_airtime } from './nodes/split_by_airtime';
import { split_by_contact_field } from './nodes/split_by_contact_field';
import { split_by_expression } from './nodes/split_by_expression';
import { split_by_groups } from './nodes/split_by_groups';
import { split_by_random } from './nodes/split_by_random';
import { split_by_run_result } from './nodes/split_by_run_result';
import { split_by_scheme } from './nodes/split_by_scheme';
import { split_by_subflow } from './nodes/split_by_subflow';
import { terminal } from './nodes/terminal';
import { split_by_ticket } from './nodes/split_by_ticket';
import { split_by_webhook } from './nodes/split_by_webhook';
import { split_by_resthook } from './nodes/split_by_resthook';
import { split_by_llm } from './nodes/split_by_llm';
import { split_by_llm_categorize } from './nodes/split_by_llm_categorize';
import { wait_for_audio } from './nodes/wait_for_audio';
import { wait_for_dial } from './nodes/wait_for_dial';
import { wait_for_digits } from './nodes/wait_for_digits';
import { wait_for_menu } from './nodes/wait_for_menu';
import { wait_for_response } from './nodes/wait_for_response';

export const ACTION_CONFIG: {
  [key: string]: ActionConfig;
} = registerConfigWithAliases({
  say_msg,
  play_audio,
  set_contact_field,
  send_broadcast,
  set_run_result,
  send_msg,
  send_email,
  start_session,
  set_contact_name,
  add_contact_groups,
  remove_contact_groups,
  set_contact_channel,
  set_contact_language,
  set_contact_status,
  add_contact_urn,
  add_input_labels,
  request_optin,
  enter_flow
});

// Helper to register a config and its aliases
function registerConfigWithAliases<T extends NodeConfig | ActionConfig>(
  config: Record<string, T>
): Record<string, T> {
  const result = { ...config };

  // Register aliases for each config
  Object.values(config).forEach((cfg) => {
    if (cfg.aliases) {
      cfg.aliases.forEach((alias) => {
        result[alias] = cfg;
      });
    }
  });

  return result;
}

export const NODE_CONFIG: {
  [key: string]: NodeConfig;
} = registerConfigWithAliases({
  execute_actions,
  split_by_contact_field,
  split_by_expression,
  split_by_groups,
  split_by_llm,
  split_by_llm_categorize,
  split_by_random,
  split_by_run_result,
  split_by_scheme,
  split_by_subflow,
  split_by_ticket,
  split_by_webhook,
  split_by_resthook,
  wait_for_menu,
  wait_for_digits,
  wait_for_audio,
  wait_for_dial,
  wait_for_response,
  split_by_airtime,
  terminal // Temporary: legacy support for terminal nodes (see AppState.ts)
});
