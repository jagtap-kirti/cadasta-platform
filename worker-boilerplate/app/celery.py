from __future__ import absolute_import

from celery import Celery


app = Celery('app',
             task_cls='app.celeryutils.Task',
             backend='app.celeryutils.ResultQueueRPC',)
app.config_from_object('app.celeryconfig')

p = app.amqp.producer_pool.acquire()
try:
    p.channel.exchange_declare(
        exchange=app.conf.result_exchange, type=app.conf.result_exchange_type)
    [p.maybe_declare(q) for q in app.conf.task_queues]
finally:
    p.release()


if __name__ == '__main__':
    app.start()
