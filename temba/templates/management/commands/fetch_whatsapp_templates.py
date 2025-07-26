"""
Django management command to fetch WhatsApp templates from Meta's API and insert them into RapidPro database.

Usage examples:
  # Create new channel and fetch templates
  python manage.py fetch_whatsapp_templates --waba-id 123456789 --access-token YOUR_TOKEN --org-id 1 --wa-number "+1234567890" --wa-verified-name "Your Business" --create-channel

  # Use existing channel
  python manage.py fetch_whatsapp_templates --waba-id 123456789 --access-token YOUR_TOKEN --channel-id 5

  # Dry run to preview templates
  python manage.py fetch_whatsapp_templates --waba-id 123456789 --access-token YOUR_TOKEN --channel-id 5 --dry-run
"""

import json
import requests
from random import randint

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from temba.channels.models import Channel
from temba.channels.types.whatsapp.type import WhatsAppType
from temba.orgs.models import Org
from temba.templates.models import TemplateTranslation
from temba.users.models import User


class Command(BaseCommand):
    help = "Fetch WhatsApp templates from Meta API and insert into RapidPro database"

    def add_arguments(self, parser):
        # Meta API credentials (required)
        parser.add_argument("--waba-id", required=True, help="WhatsApp Business Account ID")
        parser.add_argument("--access-token", required=True, help="System User Access Token for WhatsApp Business API")

        # Channel selection (either existing or create new)
        parser.add_argument("--channel-id", type=int, help="Use existing channel ID")
        parser.add_argument("--org-id", type=int, help="Organization ID (required for creating new channel)")

        # Channel creation parameters (for new channels)
        parser.add_argument("--create-channel", action="store_true", help="Create new WhatsApp channel")
        parser.add_argument("--wa-number", help="WhatsApp phone number (required for new channel)")
        parser.add_argument("--wa-verified-name", help="Verified business name (required for new channel)")
        parser.add_argument("--wa-currency", default="USD", help="Account currency (default: USD)")
        parser.add_argument("--wa-business-id", help="Facebook Business ID")
        parser.add_argument("--wa-namespace", help="Message template namespace")

        # Options
        parser.add_argument(
            "--dry-run", action="store_true", help="Fetch templates but don't insert them into database"
        )
        parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    def handle(self, *args, **options):
        self.verbosity = options["verbosity"]
        self.verbose = options.get("verbose", False)

        try:
            # 1. Validate parameters
            waba_id = options["waba_id"]
            access_token = options["access_token"]

            # 2. Get or create channel
            channel = self._get_or_create_channel(options)

            # 3. Fetch templates from Meta API
            self.stdout.write("Fetching templates from Meta WhatsApp Business API...")
            raw_templates = self._fetch_templates_from_meta(waba_id, access_token, channel)

            if not raw_templates:
                self.stdout.write(self.style.WARNING("No templates found in your WhatsApp Business Account"))
                return

            self.stdout.write(f"Found {len(raw_templates)} templates")

            # 4. Show template details if verbose
            if self.verbose or options["dry_run"]:
                self._show_template_details(raw_templates)

            # 5. Process templates (unless dry run)
            if not options["dry_run"]:
                template_count = self._process_templates(channel, raw_templates)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed {template_count} templates for channel {channel.id} ({channel.name})"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("Dry run mode - no templates were inserted"))

        except Exception as e:
            raise CommandError(f"Error: {str(e)}")

    def _get_or_create_channel(self, options):
        """Get existing channel or create a new one"""
        channel_id = options.get("channel_id")

        if channel_id:
            try:
                channel = Channel.objects.get(id=channel_id, is_active=True)
                if channel.channel_type != "WAC":
                    raise CommandError(f"Channel {channel_id} is not a WhatsApp channel")
                self.stdout.write(f"Using existing channel: {channel.id} ({channel.name})")
                return channel
            except Channel.DoesNotExist:
                raise CommandError(f"Channel with ID {channel_id} not found or inactive")

        elif options.get("create_channel"):
            return self._create_whatsapp_channel(options)

        else:
            raise CommandError("Must provide either --channel-id or --create-channel with --org-id")

    def _create_whatsapp_channel(self, options):
        """Create a new WhatsApp channel"""
        org_id = options.get("org_id")
        wa_number = options.get("wa_number")
        wa_verified_name = options.get("wa_verified_name")

        if not all([org_id, wa_number, wa_verified_name]):
            raise CommandError("For new channel, must provide --org-id, --wa-number, and --wa-verified-name")

        try:
            org = Org.objects.get(id=org_id, is_active=True)
        except Org.DoesNotExist:
            raise CommandError(f"Organization with ID {org_id} not found or inactive")

        # Get the first admin user for the org
        admin_user = org.get_admins().first()
        if not admin_user:
            raise CommandError(f"No admin users found for organization {org_id}")

        # Generate a phone number ID (normally this comes from Meta API)
        phone_number_id = f"phone_{randint(100000, 999999)}"

        # Create channel configuration
        config = {
            "wa_number": wa_number,
            "wa_verified_name": wa_verified_name,
            "wa_waba_id": options["waba_id"],
            "wa_currency": options.get("wa_currency", "USD"),
            "wa_business_id": options.get("wa_business_id", ""),
            "wa_message_template_namespace": options.get("wa_namespace", ""),
            "wa_pin": str(randint(100000, 999999)),
        }

        # Get WhatsApp channel type
        whatsapp_type = None
        for channel_type in Channel.get_types():
            if channel_type.code == "WAC":
                whatsapp_type = channel_type
                break

        if not whatsapp_type:
            raise CommandError("WhatsApp channel type not found")

        name = f"{wa_number} - {wa_verified_name}"[:64]

        channel = Channel.create(
            org,
            admin_user,
            None,
            whatsapp_type,
            name=name,
            address=phone_number_id,
            config=config,
            tps=80,
        )

        self.stdout.write(f"Created new WhatsApp channel: {channel.id} ({channel.name})")
        return channel

    def _fetch_templates_from_meta(self, waba_id, access_token, channel):
        """Fetch templates from Meta's WhatsApp Business API"""
        url = f"https://whatsapp.turn.io/graph/v14.0/{waba_id}/message_templates"
        headers = {"Authorization": f"Bearer {access_token}"}
        templates = []

        while url:
            if self.verbose:
                self.stdout.write(f"Making API request to: {url}")

            try:
                response = requests.get(url, params={"limit": 255}, headers=headers)
                response.raise_for_status()

                data = response.json()
                templates.extend(data.get("data", []))

                # Check for pagination
                url = data.get("paging", {}).get("next", None)

                if self.verbose and url:
                    self.stdout.write(f"Found pagination, continuing...")

            except requests.RequestException as e:
                raise CommandError(f"Failed to fetch templates from Meta API: {str(e)}")

        return templates

    def _show_template_details(self, raw_templates):
        """Display template details"""
        self.stdout.write("\nTemplate Details:")
        self.stdout.write("-" * 50)

        for template in raw_templates:
            status_color = self.style.SUCCESS if template.get("status") == "APPROVED" else self.style.WARNING
            self.stdout.write(
                f"Name: {template.get('name', 'N/A')}\n"
                f"  Status: {status_color(template.get('status', 'N/A'))}\n"
                f"  Language: {template.get('language', 'N/A')}\n"
                f"  ID: {template.get('id', 'N/A')}\n"
                f"  Components: {len(template.get('components', []))}\n"
            )

            if self.verbose and template.get("components"):
                for i, component in enumerate(template["components"]):
                    comp_type = component.get("type", "UNKNOWN")
                    comp_text = component.get("text", "")[:50]
                    if len(component.get("text", "")) > 50:
                        comp_text += "..."
                    self.stdout.write(f"    Component {i+1}: {comp_type} - {comp_text}")

            self.stdout.write("")

    def _process_templates(self, channel, raw_templates):
        """Process templates using existing RapidPro logic"""
        if self.verbose:
            self.stdout.write("Processing templates using RapidPro's existing sync logic...")

        # Use the existing template sync logic from RapidPro
        TemplateTranslation.update_local(channel, raw_templates)

        # Return count of templates for this channel
        return channel.template_translations.count()
