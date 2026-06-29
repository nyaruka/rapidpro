import copy

from django.test import SimpleTestCase

from temba.tests.mailroom import clone_flow_definition


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
