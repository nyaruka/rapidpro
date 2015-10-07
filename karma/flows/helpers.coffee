gettext = (text) ->
  return text

getNode = (flow, uuid) ->
  for actionset in flow.definition.action_sets
    if actionset.uuid == uuid
      return actionset

  for ruleset in flow.definition.rule_sets
    if ruleset.uuid == uuid
      return ruleset

getRule = (flow, ruleset_id, rule_id) ->
  ruleset = getNode(flow, ruleset_id)
  for rule in ruleset.rules
    if rule.uuid == rule_id
      return rule

# bootstrap our json fixtures
jasmine.getJSONFixtures().fixturesPath='base/media/test_flows';