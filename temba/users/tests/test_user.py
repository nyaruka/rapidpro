from temba.api.models import APIToken
from temba.orgs.models import OrgRole
from temba.orgs.tasks import update_members_seen
from temba.tests import TembaTest, mock_mailroom
from temba.users.models import User


class UserTest(TembaTest):
    def test_model(self):
        user = User.create("jim@rapidpro.io", "Jim", "McFlow", password="super")
        self.org.add_user(user, OrgRole.EDITOR)
        self.org2.add_user(user, OrgRole.AGENT)

        self.assertEqual("Jim McFlow", user.name)
        self.assertFalse(user.is_alpha)
        self.assertFalse(user.is_beta)
        self.assertEqual({"uuid": str(user.uuid), "name": "Jim McFlow"}, user.as_engine_ref())
        self.assertEqual([self.org, self.org2], list(user.get_orgs().order_by("id")))
        self.assertFalse(user.is_verified())
        self.assertEqual(0, user.emailaddress_set.count())

        user.set_verified(True)
        self.assertTrue(user.is_verified())
        self.assertTrue(user.emailaddress_set.filter(email="jim@rapidpro.io", primary=True, verified=True).exists())

        user.set_verified(False)
        self.assertFalse(user.is_verified())
        self.assertEqual(1, user.emailaddress_set.count())
        self.assertTrue(user.emailaddress_set.filter(email="jim@rapidpro.io", primary=True, verified=False).exists())

        user.last_name = ""
        user.save(update_fields=("last_name",))

        self.assertEqual("Jim", user.name)
        self.assertEqual({"uuid": str(user.uuid), "name": "Jim"}, user.as_engine_ref())

        self.assertEqual(user, User.objects.get_by_natural_key("jim@rapidpro.io"))
        self.assertEqual(user, User.objects.get_by_natural_key("JIM@rapidpro.io"))

    def test_has_org_perm(self):
        granter = self.create_user("jim@rapidpro.io", group_names=("Granters",))

        tests = (
            (
                self.org,
                "contacts.contact_list",
                {self.agent: False, self.admin: True, self.admin2: False},
            ),
            (
                self.org2,
                "contacts.contact_list",
                {self.agent: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org2,
                "contacts.contact_read",
                {self.agent: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org,
                "orgs.org_edit",
                {self.agent: False, self.admin: True, self.admin2: False},
            ),
            (
                self.org2,
                "orgs.org_edit",
                {self.agent: False, self.admin: False, self.admin2: True},
            ),
            (
                self.org,
                "orgs.org_grant",
                {self.agent: False, self.admin: False, self.admin2: False, granter: True},
            ),
            (
                self.org,
                "xxx.yyy_zzz",
                {self.agent: False, self.admin: False, self.admin2: False},
            ),
        )
        for org, perm, checks in tests:
            for user, has_perm in checks.items():
                self.assertEqual(
                    has_perm,
                    user.has_org_perm(org, perm),
                    f"expected {user} to{'' if has_perm else ' not'} have perm {perm} in org {org.name}",
                )

    @mock_mailroom
    def test_release(self, mr_mocks):
        token = APIToken.create(self.org, self.admin)

        # admin doesn't "own" any orgs
        self.assertEqual(0, len(self.admin.get_owned_orgs()))

        # release all but our admin
        self.editor.release(self.customer_support)
        self.agent.release(self.customer_support)

        # still a user left, our org remains active
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_active)

        # now that we are the last user, we own it now
        self.assertEqual(1, len(self.admin.get_owned_orgs()))
        self.admin.release(self.customer_support)

        # and we take our org with us
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)

        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_last_seen(self):
        membership = self.org.get_membership(self.admin)
        membership.record_seen()
        self.assertIsNone(membership.last_seen_on)

        update_members_seen()

        membership.refresh_from_db()
        self.assertIsNotNone(membership.last_seen_on)
