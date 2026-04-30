# Top-level definition fields treated as flow metadata (excludes system-managed keys
# like uuid, revision, spec_version which always differ or never change meaningfully).
_METADATA_FIELDS = ("name", "type", "expire_after_minutes")

_STICKY_LAYOUT_FIELDS = ("position", "width", "height")


def compute_changes(old: dict, new: dict) -> dict:
    """
    Diffs two flow definitions and returns a categorized summary as:
        {"tags": [...]}

    Tags are sorted strings naming the *kinds* of changes present in the new revision:
        positions  — node moves, sticky moves/resizes
        nodes      — nodes added or removed
        actions    — actions added, removed, edited, or reordered within a node
        routing    — router config or exit destinations changed
        stickies   — stickies added, removed, or content-edited
        metadata   — flow-level fields changed (name, type, expire_after_minutes, base_language)
        localization:<lang> — translations changed for that language
    """
    tags = set()

    if old.get("language") != new.get("language"):
        tags.add("metadata")
    if any(old.get(f) != new.get(f) for f in _METADATA_FIELDS):
        tags.add("metadata")

    old_nodes = {n["uuid"]: n for n in old.get("nodes") or []}
    new_nodes = {n["uuid"]: n for n in new.get("nodes") or []}

    if old_nodes.keys() ^ new_nodes.keys():
        tags.add("nodes")

    for uuid in old_nodes.keys() & new_nodes.keys():
        _tag_node_diff(old_nodes[uuid], new_nodes[uuid], tags)

    old_ui = old.get("_ui") or {}
    new_ui = new.get("_ui") or {}

    old_ui_nodes = old_ui.get("nodes") or {}
    new_ui_nodes = new_ui.get("nodes") or {}
    for uuid in old_ui_nodes.keys() & new_ui_nodes.keys():
        if old_ui_nodes[uuid].get("position") != new_ui_nodes[uuid].get("position"):
            tags.add("positions")
            break

    old_stickies = old_ui.get("stickies") or {}
    new_stickies = new_ui.get("stickies") or {}
    if old_stickies.keys() ^ new_stickies.keys():
        tags.add("stickies")
    for uuid in old_stickies.keys() & new_stickies.keys():
        old_s, new_s = old_stickies[uuid], new_stickies[uuid]
        if any(old_s.get(f) != new_s.get(f) for f in _STICKY_LAYOUT_FIELDS):
            tags.add("positions")
        # any non-layout field difference counts as a content edit, so future sticky
        # fields don't get silently dropped
        non_layout_keys = (set(old_s) | set(new_s)) - set(_STICKY_LAYOUT_FIELDS)
        if any(old_s.get(k) != new_s.get(k) for k in non_layout_keys):
            tags.add("stickies")

    old_loc = old.get("localization") or {}
    new_loc = new.get("localization") or {}
    for lang in set(old_loc) | set(new_loc):
        if (old_loc.get(lang) or {}) != (new_loc.get(lang) or {}):
            tags.add(f"localization:{lang}")

    return {"tags": sorted(tags)}


def _tag_node_diff(old: dict, new: dict, tags: set) -> None:
    old_action_list = old.get("actions") or []
    new_action_list = new.get("actions") or []
    old_actions = {a["uuid"]: a for a in old_action_list}
    new_actions = {a["uuid"]: a for a in new_action_list}

    if old_actions.keys() ^ new_actions.keys():
        tags.add("actions")
    else:
        for uuid in old_actions.keys() & new_actions.keys():
            if old_actions[uuid] != new_actions[uuid]:
                tags.add("actions")
                break
        else:
            old_order = [a["uuid"] for a in old_action_list]
            new_order = [a["uuid"] for a in new_action_list]
            if old_order != new_order:
                tags.add("actions")

    if old.get("router") != new.get("router"):
        tags.add("routing")

    old_exits = {e["uuid"]: e for e in old.get("exits") or []}
    new_exits = {e["uuid"]: e for e in new.get("exits") or []}
    for uuid in old_exits.keys() & new_exits.keys():
        if old_exits[uuid].get("destination_uuid") != new_exits[uuid].get("destination_uuid"):
            tags.add("routing")
            break
