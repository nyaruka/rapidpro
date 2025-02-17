from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.account.models import EmailAddress

from django.core.management.base import BaseCommand

from temba.users.models import User


class Command(BaseCommand):
    def handle(self, **options):
        adapter = get_adapter()
        authenticators = []

        print("Migrating MFA data...")
        backup_tokens = set()
        users = User.objects.filter(two_factor_enabled=True)
        for user in users:
            if Authenticator.objects.filter(user=user).exists():
                continue

            backup_tokens.update(user.backup_tokens.filter(is_used=False).values_list("token", flat=True))
            # tokens = [t.token for t in user.backup_tokens.filter(is_used=False)]

            totp_authenticator = Authenticator(
                user_id=user.id,
                type=Authenticator.Type.TOTP,
                data={"secret": adapter.encrypt(user.two_factor_secret)},
            )
            authenticators.append(totp_authenticator)
            authenticators.append(
                Authenticator(
                    user_id=user.id,
                    type=Authenticator.Type.RECOVERY_CODES,
                    data={
                        "migrated_codes": [adapter.encrypt(t) for t in backup_tokens],
                    },
                )
            )
            Authenticator.objects.bulk_create(authenticators)

        print(f"Created MFA for {len(users)} users")

        print("Migrating email addresses")
        users = User.objects.filter(email_status="V")
        for user in users:
            EmailAddress.objects.filter(user=user).delete()
            EmailAddress.objects.create(
                user=user,
                email=user.email,
                verified=True,
                primary=True,
            )
        print(f"Created verified email addresses for {len(users)} users")
