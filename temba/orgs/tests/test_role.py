from django.contrib.auth.models import Group

from temba.orgs.models import OrgRole
from temba.tests import TembaTest


class OrgRoleTest(TembaTest):
    def test_from_code(self):
        self.assertEqual(OrgRole.EDITOR, OrgRole.from_code("E"))
        self.assertIsNone(OrgRole.from_code("X"))

    def test_from_group(self):
        self.assertEqual(OrgRole.EDITOR, OrgRole.from_group(Group.objects.get(name="Editors")))
        self.assertIsNone(OrgRole.from_group(Group.objects.get(name="Beta")))

    def test_group(self):
        self.assertEqual(Group.objects.get(name="Editors"), OrgRole.EDITOR.group)
        self.assertEqual(Group.objects.get(name="Agents"), OrgRole.AGENT.group)
