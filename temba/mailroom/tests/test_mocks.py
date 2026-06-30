import copy

from django.test import SimpleTestCase

from temba.tests.mailroom import clone_flow_definition, inspect_flow


class InspectFlowTest(SimpleTestCase):
    def test_inspect_flow(self):
        definition = {
            "uuid": "a0a00000-0000-0000-0000-000000000000",
            "name": "Test",
            "nodes": [
                {
                    "uuid": "n1n00000-0000-0000-0000-000000000000",
                    "actions": [
                        {
                            "type": "add_contact_groups",
                            "groups": [
                                {"uuid": "b9b11111-1111-1111-1111-111111111111", "name": "Doctors"},
                                {"uuid": "b9b11111-1111-1111-1111-111111111111", "name": "Doctors"},  # duplicate
                            ],
                        },
                        {"type": "set_contact_field", "field": {"key": "gender", "name": "Gender"}},
                        {"type": "enter_flow", "flow": {}},  # malformed ref with no uuid/key is ignored
                        {"type": "set_run_result", "name": "Note", "category": "Approved"},
                        {"type": "set_run_result", "name": "Bare"},  # no category
                        {
                            "type": "send_msg",
                            "text": "you are @fields.age, @parent.fields.phone, @globals.org_name",
                            "attachments": ["image:@fields.photo"],  # expression in a list
                            "extra": {"note": "@fields.mood"},  # expression in a nested dict
                        },
                    ],
                    "router": {"result_name": "Color", "categories": [{"name": "Red"}, {"name": "Other"}]},
                },
                {
                    "uuid": "n2n00000-0000-0000-0000-000000000000",
                    "router": {
                        "operand": "@fields.region",
                        "result_name": "Color",  # same key as node 1 - merges
                        "categories": [{"name": "Blue"}, {"name": "Other"}],
                        "cases": [
                            {"type": "has_group", "arguments": ["c0c22222-2222-2222-2222-222222222222"]},  # no name
                            {"type": "has_group", "arguments": ["c1c33333-3333-3333-3333-333333333333", "Testers"]},
                            {"type": "has_any_word", "arguments": ["red"]},  # not a dependency
                        ],
                    },
                },
            ],
        }
        original = copy.deepcopy(definition)

        info = inspect_flow(definition)

        # dependencies: typed action/router refs plus field/global refs pulled from expressions, deduped
        self.assertEqual(
            [
                ("group", "b9b11111-1111-1111-1111-111111111111", "Doctors"),
                ("field", "gender", "Gender"),
                ("field", "age", ""),
                ("field", "phone", ""),  # parent.fields.phone still resolves to field key "phone"
                ("global", "org_name", ""),
                ("field", "photo", ""),
                ("field", "mood", ""),
                ("field", "region", ""),  # from the router operand, scanned before its cases
                ("group", "c0c22222-2222-2222-2222-222222222222", ""),
                ("group", "c1c33333-3333-3333-3333-333333333333", "Testers"),
            ],
            [(d["type"], d.get("uuid", d.get("key")), d["name"]) for d in info["dependencies"]],
        )
        self.assertTrue(all(d["missing"] is False for d in info["dependencies"]))

        # results: save-result actions (in node order) then routers, merged by snakified key across nodes
        self.assertEqual(
            [
                {"key": "note", "name": "Note", "categories": ["Approved"]},
                {"key": "bare", "name": "Bare", "categories": []},
                {"key": "color", "name": "Color", "categories": ["Red", "Other", "Blue"]},
            ],
            [{k: r[k] for k in ("key", "name", "categories")} for r in info["results"]],
        )
        # the Color result merges both nodes that save it
        color = next(r for r in info["results"] if r["key"] == "color")
        self.assertEqual(
            ["n1n00000-0000-0000-0000-000000000000", "n2n00000-0000-0000-0000-000000000000"], color["node_uuids"]
        )

        # the rest of the analysis isn't reproduced
        self.assertEqual([], info["issues"])
        self.assertEqual([], info["parent_refs"])

        # the input definition is not mutated
        self.assertEqual(original, definition)


class CloneFlowDefinitionTest(SimpleTestCase):
    def test_clone_flow_definition(self):
        # b9b... and c0c... are dependencies that resolve to other objects in the target org; everything else is
        # the flow's own structure which should keep its UUIDs
        mapping = {
            "b9b11111-1111-1111-1111-111111111111": "d0d11111-1111-1111-1111-111111111111",
            "c0c22222-2222-2222-2222-222222222222": "e1e22222-2222-2222-2222-222222222222",
        }
        definition = {
            "uuid": "a0a00000-0000-0000-0000-000000000000",  # flow's own uuid - unmapped, stays
            "name": "Test",
            "nodes": [
                {
                    "uuid": "a1a00000-0000-0000-0000-000000000000",  # node uuid - unmapped, stays
                    "actions": [
                        {
                            "type": "add_contact_groups",
                            "uuid": "a2a00000-0000-0000-0000-000000000000",
                            "groups": [{"uuid": "b9b11111-1111-1111-1111-111111111111", "name": "Doctors"}],  # dep
                        }
                    ],
                    "exits": [
                        {
                            "uuid": "a3a00000-0000-0000-0000-000000000000",
                            "destination_uuid": "a1a00000-0000-0000-0000-000000000000",  # *_uuid, unmapped, stays
                        }
                    ],
                }
            ],
            "_ui": {
                "c0c22222-2222-2222-2222-222222222222": {"position": {"left": 0, "top": 0}},  # dep uuid as a key
                "a1a00000-0000-0000-0000-000000000000": {"position": {"left": 1, "top": 1}},  # node uuid key, stays
            },
            "field_refs": ["c0c22222-2222-2222-2222-222222222222", "not-a-uuid"],  # uuid string in a list
        }
        original = copy.deepcopy(definition)

        cloned = clone_flow_definition(definition, mapping)

        # dependency UUIDs are remapped: as a "uuid" property value...
        self.assertEqual("d0d11111-1111-1111-1111-111111111111", cloned["nodes"][0]["actions"][0]["groups"][0]["uuid"])
        # ...as a dict key (renamed)...
        self.assertIn("e1e22222-2222-2222-2222-222222222222", cloned["_ui"])
        self.assertNotIn("c0c22222-2222-2222-2222-222222222222", cloned["_ui"])
        # ...and as a bare string in a list
        self.assertEqual("e1e22222-2222-2222-2222-222222222222", cloned["field_refs"][0])

        # the flow's own UUIDs and non-UUID values are left untouched
        self.assertEqual("a0a00000-0000-0000-0000-000000000000", cloned["uuid"])
        self.assertEqual("a1a00000-0000-0000-0000-000000000000", cloned["nodes"][0]["exits"][0]["destination_uuid"])
        self.assertIn("a1a00000-0000-0000-0000-000000000000", cloned["_ui"])
        self.assertEqual("not-a-uuid", cloned["field_refs"][1])

        # the input definition is not mutated
        self.assertEqual(original, definition)
