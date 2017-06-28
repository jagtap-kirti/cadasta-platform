from __future__ import absolute_import

from celery import Celery
from celery.signals import worker_init


@worker_init.connect
def configure_workers(sender=None, conf=None, **kwargs):
    p = app.amqp.producer_pool.acquire()
    try:
        p.channel.exchange_declare(
            exchange=app.conf.result_exchange, type=app.conf.result_exchange_type)
        p.channel.queue_bind(
            app.conf.PLATFORM_QUEUE_NAME, app.conf.result_exchange,
            routing_key='#')
        [p.maybe_declare(q) for q in app.conf.task_queues]
    finally:
        p.release()


app = Celery('app',
             task_cls='app.celeryutils.Task',
             backend='app.celeryutils.ResultQueueRPC',)
app.config_from_object('app.celeryconfig')
