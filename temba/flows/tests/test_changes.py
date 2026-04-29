from temba.flows.changes import compute_changes
from temba.tests import TembaTest


def _flow(nodes=None, ui_nodes=None, stickies=None, localization=None, **top):
    """Helper for building minimal flow definitions for diffing."""
    defn = {
        "uuid": "11111111-1111-1111-1111-111111111111",
        "name": "Flow",
        "language": "eng",
        "type": "messaging",
        "expire_after_minutes": 10080,
        "nodes": nodes or [],
        "localization": localization or {},
        "_ui": {"nodes": ui_nodes or {}, "stickies": stickies or {}},
    }
    defn.update(top)
    return defn


class ComputeChangesTest(TembaTest):
    def test_no_changes(self):
        defn = _flow()
        self.assertEqual([], compute_changes(defn, defn))

    def test_metadata_changed(self):
        old = _flow()
        new = _flow(name="Renamed")
        self.assertEqual([{"type": "metadata_changed", "field": "name"}], compute_changes(old, new))

        new = _flow(expire_after_minutes=60)
        self.assertEqual([{"type": "metadata_changed", "field": "expire_after_minutes"}], compute_changes(old, new))

    def test_base_language_changed(self):
        old = _flow()
        new = _flow(language="spa")
        self.assertEqual([{"type": "base_language_changed"}], compute_changes(old, new))

    def test_node_added_and_removed(self):
        node_a = {"uuid": "a" * 36, "actions": [], "exits": []}
        node_b = {"uuid": "b" * 36, "actions": [], "exits": []}

        self.assertEqual(
            [{"type": "node_added", "uuid": node_b["uuid"]}],
            compute_changes(_flow(nodes=[node_a]), _flow(nodes=[node_a, node_b])),
        )

        self.assertEqual(
            [{"type": "node_removed", "uuid": node_b["uuid"]}],
            compute_changes(_flow(nodes=[node_a, node_b]), _flow(nodes=[node_a])),
        )

    def test_node_moved(self):
        ui_a = {"a" * 36: {"position": {"left": 0, "top": 0}, "type": "execute_actions"}}
        ui_a_moved = {"a" * 36: {"position": {"left": 50, "top": 50}, "type": "execute_actions"}}

        self.assertEqual(
            [{"type": "node_moved", "uuid": "a" * 36}],
            compute_changes(_flow(ui_nodes=ui_a), _flow(ui_nodes=ui_a_moved)),
        )

        # type-only change in _ui shouldn't register as a move
        ui_a_retyped = {"a" * 36: {"position": {"left": 0, "top": 0}, "type": "wait_for_response"}}
        self.assertEqual([], compute_changes(_flow(ui_nodes=ui_a), _flow(ui_nodes=ui_a_retyped)))

    def test_action_added_removed_updated(self):
        action_send = {"uuid": "ac" + "0" * 34, "type": "send_msg", "text": "hello"}
        action_field = {"uuid": "ac" + "1" * 34, "type": "set_contact_field", "field": "x", "value": "1"}

        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [action_send], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [action_send, action_field], "exits": []}])
        self.assertEqual(
            [
                {
                    "type": "action_added",
                    "node": "n" * 36,
                    "uuid": action_field["uuid"],
                    "subtype": "set_contact_field",
                }
            ],
            compute_changes(old, new),
        )

        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [action_send, action_field], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [action_send], "exits": []}])
        self.assertEqual(
            [
                {
                    "type": "action_removed",
                    "node": "n" * 36,
                    "uuid": action_field["uuid"],
                    "subtype": "set_contact_field",
                }
            ],
            compute_changes(old, new),
        )

        edited = {**action_send, "text": "goodbye"}
        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [action_send], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [edited], "exits": []}])
        self.assertEqual(
            [
                {
                    "type": "action_updated",
                    "node": "n" * 36,
                    "uuid": action_send["uuid"],
                    "subtype": "send_msg",
                }
            ],
            compute_changes(old, new),
        )

    def test_action_reordered(self):
        a1 = {"uuid": "ac" + "0" * 34, "type": "send_msg", "text": "hello"}
        a2 = {"uuid": "ac" + "1" * 34, "type": "send_msg", "text": "world"}
        a3 = {"uuid": "ac" + "2" * 34, "type": "send_msg", "text": "!"}

        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [a1, a2, a3], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [a3, a1, a2], "exits": []}])
        self.assertEqual([{"type": "action_reordered", "node": "n" * 36}], compute_changes(old, new))

        # adding a new action that displaces order is just an add, not a reorder
        a4 = {"uuid": "ac" + "3" * 34, "type": "send_msg", "text": "new"}
        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [a1, a2], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [a4, a1, a2], "exits": []}])
        self.assertEqual(
            [{"type": "action_added", "node": "n" * 36, "uuid": a4["uuid"], "subtype": "send_msg"}],
            compute_changes(old, new),
        )

        # reorder + edit produces both records
        a1_edited = {**a1, "text": "hi"}
        old = _flow(nodes=[{"uuid": "n" * 36, "actions": [a1, a2], "exits": []}])
        new = _flow(nodes=[{"uuid": "n" * 36, "actions": [a2, a1_edited], "exits": []}])
        self.assertEqual(
            [
                {"type": "action_updated", "node": "n" * 36, "uuid": a1["uuid"], "subtype": "send_msg"},
                {"type": "action_reordered", "node": "n" * 36},
            ],
            compute_changes(old, new),
        )

    def test_router_updated(self):
        old_node = {
            "uuid": "n" * 36,
            "actions": [],
            "exits": [{"uuid": "e" * 36}],
            "router": {"type": "switch", "operand": "@input.text", "categories": []},
        }
        new_node = {**old_node, "router": {**old_node["router"], "operand": "@contact.name"}}

        self.assertEqual(
            [{"type": "router_updated", "node": "n" * 36, "subtype": "switch"}],
            compute_changes(_flow(nodes=[old_node]), _flow(nodes=[new_node])),
        )

    def test_connection_changed(self):
        old_node = {
            "uuid": "n" * 36,
            "actions": [],
            "exits": [{"uuid": "e" * 36, "destination_uuid": None}],
        }
        new_node = {**old_node, "exits": [{"uuid": "e" * 36, "destination_uuid": "x" * 36}]}

        self.assertEqual(
            [{"type": "connection_changed", "node": "n" * 36, "uuid": "e" * 36}],
            compute_changes(_flow(nodes=[old_node]), _flow(nodes=[new_node])),
        )

    def test_stickies(self):
        sticky = {
            "position": {"left": 0, "top": 0},
            "title": "Hello",
            "body": "World",
            "color": "yellow",
        }

        # added
        self.assertEqual(
            [{"type": "sticky_added", "uuid": "s" * 36}],
            compute_changes(_flow(), _flow(stickies={"s" * 36: sticky})),
        )

        # removed
        self.assertEqual(
            [{"type": "sticky_removed", "uuid": "s" * 36}],
            compute_changes(_flow(stickies={"s" * 36: sticky}), _flow()),
        )

        # moved (position only)
        moved = {**sticky, "position": {"left": 100, "top": 50}}
        self.assertEqual(
            [{"type": "sticky_moved", "uuid": "s" * 36}],
            compute_changes(_flow(stickies={"s" * 36: sticky}), _flow(stickies={"s" * 36: moved})),
        )

        # resized counts as moved
        resized = {**sticky, "width": 300}
        self.assertEqual(
            [{"type": "sticky_moved", "uuid": "s" * 36}],
            compute_changes(_flow(stickies={"s" * 36: sticky}), _flow(stickies={"s" * 36: resized})),
        )

        # content updated
        edited = {**sticky, "body": "Goodbye"}
        self.assertEqual(
            [{"type": "sticky_updated", "uuid": "s" * 36}],
            compute_changes(_flow(stickies={"s" * 36: sticky}), _flow(stickies={"s" * 36: edited})),
        )

        # both move AND content update produces both records
        moved_and_edited = {**sticky, "position": {"left": 100, "top": 50}, "title": "New"}
        self.assertEqual(
            [
                {"type": "sticky_moved", "uuid": "s" * 36},
                {"type": "sticky_updated", "uuid": "s" * 36},
            ],
            compute_changes(_flow(stickies={"s" * 36: sticky}), _flow(stickies={"s" * 36: moved_and_edited})),
        )

    def test_translations(self):
        item_uuid = "t" * 36

        # added
        self.assertEqual(
            [{"type": "translation_added", "lang": "spa", "uuid": item_uuid}],
            compute_changes(_flow(), _flow(localization={"spa": {item_uuid: {"text": "hola"}}})),
        )

        # removed
        self.assertEqual(
            [{"type": "translation_removed", "lang": "spa", "uuid": item_uuid}],
            compute_changes(_flow(localization={"spa": {item_uuid: {"text": "hola"}}}), _flow()),
        )

        # updated
        self.assertEqual(
            [{"type": "translation_updated", "lang": "spa", "uuid": item_uuid}],
            compute_changes(
                _flow(localization={"spa": {item_uuid: {"text": "hola"}}}),
                _flow(localization={"spa": {item_uuid: {"text": "buenas"}}}),
            ),
        )

    def test_combined_changes(self):
        # multiple unrelated edits in a single save produce one record per edit
        node_a = {"uuid": "a" * 36, "actions": [], "exits": []}
        node_b = {"uuid": "b" * 36, "actions": [], "exits": []}
        ui_a = {"a" * 36: {"position": {"left": 0, "top": 0}}}
        ui_a_moved = {"a" * 36: {"position": {"left": 50, "top": 50}}}

        old = _flow(nodes=[node_a], ui_nodes=ui_a)
        new = _flow(nodes=[node_a, node_b], ui_nodes=ui_a_moved, name="Renamed")

        changes = compute_changes(old, new)
        self.assertIn({"type": "metadata_changed", "field": "name"}, changes)
        self.assertIn({"type": "node_added", "uuid": "b" * 36}, changes)
        self.assertIn({"type": "node_moved", "uuid": "a" * 36}, changes)
        self.assertEqual(3, len(changes))
