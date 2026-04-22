import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0080_squashed"),
        ("templates", "0047_squashed"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaignevent",
            name="template",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="templates.template",
            ),
        ),
        migrations.AddField(
            model_name="campaignevent",
            name="template_variables",
            field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), null=True, size=None),
        ),
    ]
