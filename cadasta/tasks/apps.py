from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = 'tasks'

    def ready(self):
        # from . import signals  # NOQA
        from .celery import app
        from .steps import MessageConsumer, DisableQueues

        app.steps['worker'].add(DisableQueues)
        app.steps['consumer'].add(MessageConsumer)
        app.autodiscover_tasks(force=True)

        # Setup exchanges
        with app.producer_or_acquire() as P:
            # Ensure all queues are registered with proper exchanges
            for q in app.amqp.queues.values():
                P.maybe_declare(q)
