from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("campaigns", "0025_auto_20180615_2040")]

    operations = [
        migrations.AddField(
            model_name="campaignevent",
            name="use_created_on",
            field=models.BooleanField(
                default=False, help_text="Use timestamp when contact was created to trigger the event"
            ),
        )
    ]
