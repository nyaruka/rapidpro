# Generated by Django 1.11.6 on 2018-07-16 20:43

from django.contrib.auth.hashers import make_password
from django.db import migrations

ANONYMOUS_USER_NAME = "AnonymousUser"


def ensure_anon_user_exists(apps, schema_editor):
    User = apps.get_model("users", "User")

    if not User.objects.filter(username=ANONYMOUS_USER_NAME).exists():  # pragma: no cover
        user = User(username=ANONYMOUS_USER_NAME)
        user.password = make_password(None)
        user.save()


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial"), ("orgs", "0163_squashed")]

    operations = [migrations.RunPython(ensure_anon_user_exists)]
