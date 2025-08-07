from django.core.management import call_command

from temba.tests import TembaTest


class MigrateFlowsTest(TembaTest):
    def test_command(self):
        call_command("migrate_flows")


class InspectFlowsTest(TembaTest):
    def test_command(self):
        # flow which wrongly has has_issues set
        flow1 = self.create_flow("No Problems")
        flow1.has_issues = True
        flow1.save(update_fields=("has_issues",))

        # create flow with a bad_regex issue but clear has_issues
        flow2 = self.create_flow(
            "Bad Regex",
            nodes=[
                {
                    "uuid": "f3d5ccd0-fee0-4955-bcb7-21613f049eae",
                    "router": {
                        "type": "switch",
                        "categories": [
                            {
                                "uuid": "fc4ee6b0-af6f-42e3-ae84-153c313e390a",
                                "name": "Bad Regex",
                                "exit_uuid": "72a3f1da-bde1-4549-a986-d35809807be8",
                            },
                            {
                                "uuid": "78ae8f05-f92e-43b2-a886-406eaea1b8e0",
                                "name": "Other",
                                "exit_uuid": "72a3f1da-bde1-4549-a986-d35809807be8",
                            },
                        ],
                        "default_category_uuid": "78ae8f05-f92e-43b2-a886-406eaea1b8e0",
                        "operand": "@input.text",
                        "cases": [
                            {
                                "uuid": "98503572-25bf-40ce-ad72-8836b6549a38",
                                "type": "has_pattern",
                                "arguments": ["[["],
                                "category_uuid": "fc4ee6b0-af6f-42e3-ae84-153c313e390a",
                            }
                        ],
                    },
                    "exits": [{"uuid": "72a3f1da-bde1-4549-a986-d35809807be8"}],
                }
            ],
        )
        flow2.has_issues = False
        flow2.save(update_fields=("has_issues",))

        # create an invalid flow
        flow3 = self.create_flow("Invalid", nodes=[])
        flow3.revisions.all().update(definition={"foo": "bar"})

        call_command("inspect_flows")

        flow1.refresh_from_db()
        self.assertFalse(flow1.has_issues)

        flow2.refresh_from_db()
        self.assertTrue(flow2.has_issues)

        flow3.refresh_from_db()
        self.assertFalse(flow3.has_issues)
