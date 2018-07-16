import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("campaigns", "0026_campaignevent_use_created_on")]

    operations = [
        migrations.AlterField(
            model_name="campaignevent",
            name="relative_to",
            field=models.ForeignKey(
                blank=True,
                help_text="The field our offset is relative to",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="campaigns",
                to="contacts.ContactField",
            ),
        )
    ]
