import os

import celery

from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "temba.settings")


class TembaCelery(celery.Celery):
    def gen_task_name(self, name, module):
        """
        Just use func name for task name
        """
        return name


app = TembaCelery("temba")
app.config_from_object("django.conf:settings", namespace="CELERY")


@app.on_after_configure.connect
def configure_redbeat(sender, **kwargs):
    """
    RedBeat looks for its settings as un-namespaced keys on the celery conf so they can't come from Django settings.
    Deriving them from the broker settings here also means they track any deployment overrides of those.
    """
    sender.conf.redbeat_redis_url = sender.conf.broker_url
    sender.conf.redbeat_redis_options = {**sender.conf.broker_transport_options, "retry_period": 60}
    sender.conf.redbeat_lock_timeout = sender.conf.beat_max_loop_interval * 3


app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(("temba.channels.types.turn",))
