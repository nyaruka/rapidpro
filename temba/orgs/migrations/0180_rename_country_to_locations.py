from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0179_orgmembership_can_assign_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="org",
            old_name="country",
            new_name="locations",
        ),
    ]
