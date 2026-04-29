# Top-level definition fields treated as flow metadata (excludes system-managed keys
# like uuid, revision, spec_version which always differ or never change meaningfully).
_METADATA_FIELDS = ("name", "type", "expire_after_minutes")

# Sticky fields considered "layout" vs "content" so a save that only repositions/resizes
# a sticky doesn't get tagged as a content edit.
_STICKY_LAYOUT_FIELDS = ("position", "width", "height")
_STICKY_CONTENT_FIELDS = ("title", "body", "color")


def compute_changes(old: dict, new: dict) -> list:
    """
    Diffs two flow definitions and returns a list of change records describing what changed.

    Each record has a `type` plus identifiers for the affected entity, e.g.:
        {"type": "node_moved", "uuid": "<node-uuid>"}
        {"type": "action_updated", "node": "<node-uuid>", "uuid": "<action-uuid>", "subtype": "send_msg"}
        {"type": "translation_updated", "lang": "spa", "uuid": "<item-uuid>"}
        {"type": "metadata_changed", "field": "name"}
    """
    changes = []

    if old.get("language") != new.get("language"):
        changes.append({"type": "base_language_changed"})

    for field in _METADATA_FIELDS:
        if old.get(field) != new.get(field):
            changes.append({"type": "metadata_changed", "field": field})

    old_nodes = {n["uuid"]: n for n in old.get("nodes") or []}
    new_nodes = {n["uuid"]: n for n in new.get("nodes") or []}

    for uuid in new_nodes.keys() - old_nodes.keys():
        changes.append({"type": "node_added", "uuid": uuid})
    for uuid in old_nodes.keys() - new_nodes.keys():
        changes.append({"type": "node_removed", "uuid": uuid})
    for uuid in old_nodes.keys() & new_nodes.keys():
        changes.extend(_compare_node(old_nodes[uuid], new_nodes[uuid]))

    old_ui = old.get("_ui") or {}
    new_ui = new.get("_ui") or {}

    old_ui_nodes = old_ui.get("nodes") or {}
    new_ui_nodes = new_ui.get("nodes") or {}
    for uuid in old_ui_nodes.keys() & new_ui_nodes.keys():
        if old_ui_nodes[uuid].get("position") != new_ui_nodes[uuid].get("position"):
            changes.append({"type": "node_moved", "uuid": uuid})

    old_stickies = old_ui.get("stickies") or {}
    new_stickies = new_ui.get("stickies") or {}
    for uuid in new_stickies.keys() - old_stickies.keys():
        changes.append({"type": "sticky_added", "uuid": uuid})
    for uuid in old_stickies.keys() - new_stickies.keys():
        changes.append({"type": "sticky_removed", "uuid": uuid})
    for uuid in old_stickies.keys() & new_stickies.keys():
        old_s, new_s = old_stickies[uuid], new_stickies[uuid]
        if any(old_s.get(f) != new_s.get(f) for f in _STICKY_LAYOUT_FIELDS):
            changes.append({"type": "sticky_moved", "uuid": uuid})
        if any(old_s.get(f) != new_s.get(f) for f in _STICKY_CONTENT_FIELDS):
            changes.append({"type": "sticky_updated", "uuid": uuid})

    old_loc = old.get("localization") or {}
    new_loc = new.get("localization") or {}
    for lang in set(old_loc) | set(new_loc):
        old_lang = old_loc.get(lang) or {}
        new_lang = new_loc.get(lang) or {}
        for item_uuid in new_lang.keys() - old_lang.keys():
            changes.append({"type": "translation_added", "lang": lang, "uuid": item_uuid})
        for item_uuid in old_lang.keys() - new_lang.keys():
            changes.append({"type": "translation_removed", "lang": lang, "uuid": item_uuid})
        for item_uuid in old_lang.keys() & new_lang.keys():
            if old_lang[item_uuid] != new_lang[item_uuid]:
                changes.append({"type": "translation_updated", "lang": lang, "uuid": item_uuid})

    return changes


def _compare_node(old: dict, new: dict) -> list:
    changes = []
    node_uuid = new["uuid"]

    old_action_list = old.get("actions") or []
    new_action_list = new.get("actions") or []
    old_actions = {a["uuid"]: a for a in old_action_list}
    new_actions = {a["uuid"]: a for a in new_action_list}

    for uuid in new_actions.keys() - old_actions.keys():
        a = new_actions[uuid]
        changes.append({"type": "action_added", "node": node_uuid, "uuid": uuid, "subtype": a.get("type")})
    for uuid in old_actions.keys() - new_actions.keys():
        a = old_actions[uuid]
        changes.append({"type": "action_removed", "node": node_uuid, "uuid": uuid, "subtype": a.get("type")})
    for uuid in old_actions.keys() & new_actions.keys():
        if old_actions[uuid] != new_actions[uuid]:
            changes.append(
                {
                    "type": "action_updated",
                    "node": node_uuid,
                    "uuid": uuid,
                    "subtype": new_actions[uuid].get("type"),
                }
            )

    # detect reorder: sequence of common action uuids differs between old and new
    common = old_actions.keys() & new_actions.keys()
    old_order = [a["uuid"] for a in old_action_list if a["uuid"] in common]
    new_order = [a["uuid"] for a in new_action_list if a["uuid"] in common]
    if old_order != new_order:
        changes.append({"type": "action_reordered", "node": node_uuid})

    old_router = old.get("router")
    new_router = new.get("router")
    if old_router != new_router:
        record = {"type": "router_updated", "node": node_uuid}
        subtype = (new_router or old_router or {}).get("type")
        if subtype:
            record["subtype"] = subtype
        changes.append(record)

    old_exits = {e["uuid"]: e for e in old.get("exits") or []}
    new_exits = {e["uuid"]: e for e in new.get("exits") or []}
    for uuid in old_exits.keys() & new_exits.keys():
        if old_exits[uuid].get("destination_uuid") != new_exits[uuid].get("destination_uuid"):
            changes.append({"type": "connection_changed", "node": node_uuid, "uuid": uuid})

    return changes
