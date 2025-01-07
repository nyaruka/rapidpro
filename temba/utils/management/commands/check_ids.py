from django.apps import apps
from django.core.management import BaseCommand
from django.db.models.fields import BigIntegerField, IntegerField, SmallIntegerField


class Command(BaseCommand):
    help = "Check the database IDs for models and estimates percentage used for the sequence"

    def handle(self, *args, **kwargs):
        app_models = apps.get_models()
        for i, app_model in enumerate(app_models):
            if i == 0:
                print("-" * 120)
                print(f"{'Model Name': <64}| {'max ID': >20} | {'Type': >10} |   Percentage")
                print("-" * 120)
            if app_model.objects.exists():
                if hasattr(app_model, "id"):
                    percentage_used = None
                    fied_type = "int"
                    max_id = app_model.objects.order_by("-id").first().id
                    if isinstance(app_model.id.field, BigIntegerField):
                        percentage_used = (max_id / 9223372036854775807) * 100
                        fied_type = "bigint"
                    elif isinstance(app_model.id.field, SmallIntegerField):
                        percentage_used = (max_id / 32767) * 100
                        fied_type = "smallint"
                    elif isinstance(app_model.id.field, IntegerField):
                        percentage_used = (max_id / 2147483647) * 100
                    if percentage_used is not None:
                        print(
                            f"{str(app_model): <64}| {str(max_id): >20} | {fied_type: >10} |   {percentage_used:.3f}%"
                        )
