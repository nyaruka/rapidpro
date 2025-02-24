import pyotp

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager as AuthUserManager
from django.core.files.storage import storages
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.utils.fields import UploadToIdPathAndRename
from temba.utils.text import generate_secret, generate_token
from temba.utils.uuid import uuid4


class RecoveryToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recovery_tokens")
    token = models.CharField(max_length=32, unique=True)
    created_on = models.DateTimeField(default=timezone.now)


class FailedLogin(models.Model):
    username = models.CharField(max_length=256)
    failed_on = models.DateTimeField(default=timezone.now)


class BackupToken(models.Model):
    """
    A 2FA backup token for a user
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="backup_tokens", on_delete=models.PROTECT)
    token = models.CharField(max_length=18, unique=True, default=generate_token)
    is_used = models.BooleanField(default=False)
    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def generate_for_user(cls, user, count: int = 10):
        # delete any existing tokens for this user
        user.backup_tokens.all().delete()

        return [cls.objects.create(user=user) for i in range(count)]

    def __str__(self):
        return self.token


class UserManager(AuthUserManager):
    """
    Overrides the default user manager to make username lookups case insensitive
    """

    def get_by_natural_key(self, email: str):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": email})

    def create_user(self, email: str, password: str, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_system_user(self):
        """
        Creates the system user
        """
        user = self.model(email=User.SYSTEM["email"], first_name=User.SYSTEM["first_name"], is_system=True)
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    SYSTEM = {"email": "system", "first_name": "System"}

    STATUS_UNVERIFIED = "U"
    STATUS_VERIFIED = "V"
    STATUS_FAILING = "F"
    STATUS_CHOICES = (
        (STATUS_UNVERIFIED, _("Unverified")),
        (STATUS_VERIFIED, _("Verified")),
        (STATUS_FAILING, _("Failing")),
    )

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    # username is on its way out
    username = models.CharField(_("username"), max_length=150, null=True)

    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    email = models.EmailField(_("email address"), unique=True)
    language = models.CharField(max_length=8, choices=settings.LANGUAGES, default=settings.DEFAULT_LANGUAGE)
    avatar = models.ImageField(upload_to=UploadToIdPathAndRename("avatars/"), storage=storages["public"], null=True)

    date_joined = models.DateTimeField(default=timezone.now)
    last_auth_on = models.DateTimeField(null=True)
    is_system = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # email verification
    email_status = models.CharField(max_length=1, default=STATUS_UNVERIFIED, choices=STATUS_CHOICES)
    email_verification_secret = models.CharField(max_length=64, db_index=True)

    # 2FA support
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=16)

    # optional customer support fields
    external_id = models.CharField(max_length=128, null=True)
    verification_token = models.CharField(max_length=64, null=True)

    objects = UserManager()

    def clean(self):
        super().clean()

        self.email = self.__class__.objects.normalize_email(self.email)

    def save(self, **kwargs):
        if not self.id:
            self.two_factor_secret = pyotp.random_base32()
            self.email_verification_secret = generate_secret(64)

        return super().save(**kwargs)

    @classmethod
    def create(cls, email: str, first_name: str, last_name: str, password: str, language: str = None):
        assert not cls.get_by_email(email), "user with this email already exists"

        return cls.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            language=language or settings.DEFAULT_LANGUAGE,
        )

    @classmethod
    def get_or_create(cls, email: str, first_name: str, last_name: str, password: str, language: str = None):
        obj = cls.get_by_email(email)
        if obj:
            obj.first_name = first_name
            obj.last_name = last_name
            obj.save(update_fields=("first_name", "last_name"))
            return obj

        return cls.create(email, first_name, last_name, password=password, language=language)

    @classmethod
    def get_by_email(cls, email: str):
        return cls.objects.filter(email__iexact=email).first()

    @classmethod
    def get_orgs_for_request(cls, request):
        """
        Gets the orgs that the logged in user has a membership of.
        """

        return request.user.orgs.filter(is_active=True).order_by("name")

    @classmethod
    def get_system_user(cls):
        """
        Gets the system user
        """
        return cls.objects.get(email=cls.SYSTEM["email"])

    @property
    def name(self) -> str:
        return self.get_full_name()

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_orgs(self):
        return self.orgs.filter(is_active=True).order_by("name")

    def get_owned_orgs(self):
        """
        Gets the orgs where this user is the only user.
        """
        owned_orgs = []
        for org in self.get_orgs():
            if not org.users.exclude(id=self.id).exists():
                owned_orgs.append(org)
        return owned_orgs

    def record_auth(self):
        """
        Records that this user authenticated
        """

        self.last_auth_on = timezone.now()
        self.save(update_fields=("last_auth_on",))

    def enable_2fa(self):
        """
        Enables 2FA for this user
        """

        self.two_factor_enabled = True
        self.save(update_fields=("two_factor_enabled",))

        BackupToken.generate_for_user(self)

    def disable_2fa(self):
        """
        Disables 2FA for this user
        """

        self.two_factor_enabled = False
        self.save(update_fields=("two_factor_enabled",))

        self.backup_tokens.all().delete()

    def verify_2fa(self, *, otp: str = None, backup_token: str = None) -> bool:
        """
        Verifies a user using a 2FA mechanism (OTP or backup token)
        """
        if otp:
            return pyotp.TOTP(self.two_factor_secret).verify(otp, valid_window=2)
        elif backup_token:
            token = self.backup_tokens.filter(token=backup_token, is_used=False).first()
            if token:
                token.is_used = True
                token.save(update_fields=("is_used",))
                return True

        return False

    @cached_property
    def is_alpha(self) -> bool:
        return self.groups.filter(name="Alpha").exists()

    @cached_property
    def is_beta(self) -> bool:
        return self.groups.filter(name="Beta").exists()

    def has_org_perm(self, org, permission: str) -> bool:
        """
        Determines if a user has the given permission in the given org.
        """

        # has it innately? e.g. Granter group
        if self.has_perm(permission):
            return True

        role = org.get_user_role(self)
        if not role:
            return False

        return role.has_perm(permission)

    def get_api_tokens(self, org):
        """
        Gets this users active API tokens for the given org
        """
        return self.api_tokens.filter(org=org, is_active=True)

    def as_engine_ref(self) -> dict:
        return {"email": self.email, "name": self.name}

    def release(self, user):
        """
        Releases this user, and any orgs of which they are the sole owner.
        """
        self.first_name = ""
        self.last_name = ""
        self.email = str(uuid4())
        self.password = ""
        self.is_active = False
        self.save()

        # release any API tokens
        self.api_tokens.update(is_active=False)

        # release any orgs we own
        for org in self.get_owned_orgs():
            org.release(user, release_users=False)

        # remove user from all roles on other orgs
        for org in self.get_orgs():
            org.remove_user(self)

    def __str__(self):
        return self.name or self.email

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
