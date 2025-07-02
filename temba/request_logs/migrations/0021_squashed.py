# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("airtime", "0036_squashed"),
        ("channels", "0206_squashed"),
        ("flows", "0387_squashed"),
        ("orgs", "0171_squashed"),
        ("request_logs", "0020_remove_httplog_request_log_classif_8a1320_idx_and_more"),
    ]

    operations = []
