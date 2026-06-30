import itertools
import random
from zoneinfo import ZoneInfo

from django_valkey import get_valkey_connection

from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from temba.contacts.models import URN, Contact, ContactField, ContactGroup, ContactGroupCount, ContactURN
from temba.orgs.models import Org
from temba.users.models import User
from temba.utils import uuid

# by default every user (including the admins) gets this password
USER_PASSWORD = "Qwerty123"

# contact fields created for each org, as (key, label, value_type)
FIELDS = (
    ("age", "Age", ContactField.TYPE_NUMBER),
    ("gender", "Gender", ContactField.TYPE_TEXT),
)

# pool of names randomly assigned to generated contacts
NAMES = ("Ann", "Bob", "Cat", "Dan", "Eve", "Fay", "Gil", "Hal", "Ivy", "Jay")


class Command(BaseCommand):
    help = (
        "Creates a simple database for local development: N orgs each with an admin, a couple of fields, a group, "
        "and a share of M contacts spread across them. Requires an empty database (run migrate first)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--orgs", type=int, dest="num_orgs", default=1, help="number of orgs to create")
        parser.add_argument("--contacts", type=int, dest="num_contacts", default=100, help="total contacts to create")
        parser.add_argument("--seed", type=int, dest="seed", default=None, help="seed for deterministic UUIDs")
        parser.add_argument("--password", type=str, dest="password", default=USER_PASSWORD, help="admin password")

    def handle(self, num_orgs, num_contacts, seed, password, *args, **kwargs):
        if Org.objects.exists():
            raise CommandError("Can't generate content in a non-empty database.")

        # seed the UUID generator and our randomness so a given seed is reproducible
        seed = seed if seed is not None else random.randrange(0, 65536)
        self.random = random.Random(seed)
        uuid.default_generator = uuid.seeded_generator(seed)

        self._log(f"Generating {num_orgs} org(s) and {num_contacts} contact(s) (seed={seed})...\n")

        # fresh database so clear out the cache
        get_valkey_connection().flushdb()

        orgs = [self.create_org(i, password) for i in range(num_orgs)]
        self.create_contacts(orgs, num_contacts)

        admin = orgs[0].get_admins().first()
        self._log("\n" + self.style.SUCCESS("Done!") + f" Log in as {admin.email} / {password}\n")

    def create_org(self, index, password):
        name = f"Org {index + 1}"
        self._log(f"Creating {name}... ")

        admin = User.objects.create_user(f"admin{index + 1}@temba.io", password, is_staff=True, first_name="Admin")

        # Org.create adds the admin, sets up system groups/fields, and imports the sample flows
        org = Org.create(admin, name, ZoneInfo("America/Los_Angeles"))

        # a couple of user fields and a manual group to make the workspace feel populated
        org.cache_fields = {
            key: ContactField.create(org, admin, label, value_type) for key, label, value_type in FIELDS
        }
        org.cache_group = ContactGroup.create_manual(org, admin, "Customers")
        org.cache_admin = admin

        self._ok()
        return org

    def create_contacts(self, orgs, num_contacts):
        self._log(f"Creating {num_contacts} contacts... ")

        # spread contacts evenly across orgs, bulk inserting in batches to keep memory flat. Active-group
        # membership and group counts are maintained by db triggers, so we only insert contacts, their URNs
        # and manual group membership directly.
        for batch in itertools.batched(range(num_contacts), 5000):
            contacts = []
            for i in batch:
                org = orgs[i % len(orgs)]
                age = self.random.randint(16, 80)
                gender = self.random.choice(("M", "F"))
                contacts.append(
                    Contact(
                        org=org,
                        name=self.random.choice(NAMES),
                        language="eng",
                        status=Contact.STATUS_ACTIVE,
                        created_by=org.cache_admin,
                        modified_by=org.cache_admin,
                        created_on=timezone.now(),
                        modified_on=timezone.now(),
                        fields={
                            str(org.cache_fields["age"].uuid): {"text": str(age), "number": str(age)},
                            str(org.cache_fields["gender"].uuid): {"text": gender},
                        },
                    )
                )

            Contact.objects.bulk_create(contacts)

            urns, memberships = [], []
            for contact, i in zip(contacts, batch):
                tel = "+1206555%04d" % i
                urns.append(
                    ContactURN(
                        org=contact.org,
                        contact=contact,
                        scheme=URN.TEL_SCHEME,
                        path=tel,
                        identity=URN.from_tel(tel),
                        priority=50,
                    )
                )
                memberships.append(ContactGroup.contacts.through(contact=contact, contactgroup=contact.org.cache_group))

            ContactURN.objects.bulk_create(urns)
            ContactGroup.contacts.through.objects.bulk_create(memberships)

        ContactGroupCount.squash()
        self._ok()

    def _log(self, text):
        self.stdout.write(text, ending="")
        self.stdout.flush()

    def _ok(self):
        self.stdout.write(self.style.SUCCESS("OK"))
