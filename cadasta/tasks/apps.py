from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = 'tasks'

    def ready(self):
        from .celery import app
        app.autodiscover_tasks(force=True)

        # Setup exchanges
        with app.producer_or_acquire() as P:
            # Ensure all queues are registered with proper exchanges
            for q in app.amqp.queues.values():
                P.maybe_declare(q)
