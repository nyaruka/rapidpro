from zoneinfo import ZoneInfo

from django.core.management import BaseCommand, CommandError

from temba.contacts.models import Contact, ContactField, ContactGroup
from temba.orgs.models import Org
from temba.users.models import User

# default credentials for the admin user created by this command
DEFAULT_EMAIL = "admin@temba.io"
DEFAULT_PASSWORD = "Qwerty123"

# a few contact fields to make the workspace feel populated
FIELDS = (
    ("Age", ContactField.TYPE_NUMBER),
    ("Gender", ContactField.TYPE_TEXT),
)

# sample contacts created in the "Customers" group
CONTACTS = (
    ("Ann", "tel:+12065550101", {"age": "29", "gender": "F"}),
    ("Bob", "tel:+12065550102", {"age": "41", "gender": "M"}),
    ("Cat", "tel:+12065550103", {"age": "35", "gender": "F"}),
)


class Command(BaseCommand):
    help = "Creates a minimal database for local development (one admin, one workspace, a few contacts). Requires a running mailroom as contact creation goes through it."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"admin email (default: {DEFAULT_EMAIL})")
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="admin password")
        parser.add_argument("--org", default="Temba", help="workspace name (default: Temba)")
        parser.add_argument("--timezone", default="America/Los_Angeles", help="workspace timezone")

    def handle(self, email, password, org, timezone, *args, **kwargs):
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"A user with email {email} already exists - nothing to do.")

        self._log(f"Creating admin user {email}... ")
        admin = User.objects.create_user(email, password, is_superuser=True, is_staff=True, first_name="Admin")
        self._ok()

        self._log(f"Creating workspace {org}... ")
        # Org.create adds the user as administrator, sets up system groups/fields, and imports sample flows
        workspace = Org.create(admin, org, ZoneInfo(timezone))
        self._ok()

        self._log(f"Creating {len(FIELDS)} fields... ")
        fields = {name.lower(): ContactField.create(workspace, admin, name, value_type) for name, value_type in FIELDS}
        self._ok()

        self._log("Creating Customers group... ")
        group = ContactGroup.create_manual(workspace, admin, "Customers")
        self._ok()

        self._log(f"Creating {len(CONTACTS)} contacts... ")
        for name, urn, values in CONTACTS:
            Contact.create(
                workspace,
                admin,
                name=name,
                language="",
                status=Contact.STATUS_ACTIVE,
                urns=[urn],
                fields={fields[key]: val for key, val in values.items()},
                groups=[group],
            )
        self._ok()

        self._log("\n" + self.style.SUCCESS("Done!") + f" Log in as {email} / {password}\n")

    def _log(self, text):
        self.stdout.write(text, ending="")
        self.stdout.flush()

    def _ok(self):
        self.stdout.write(self.style.SUCCESS("OK"))
