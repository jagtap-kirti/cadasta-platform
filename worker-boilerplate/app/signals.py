from celery.signals import worker_init


@worker_init.connect
def setup_exchanges(**kwargs):
    """ Setup result exchange to route all tasks to platform queue """
    from .celery import app
    p = app.amqp.producer_pool.acquire()
    try:
        # Result Exchange
        p.channel.exchange_declare(
            exchange=app.conf.result_exchange, type=app.conf.result_exchange_type)
        p.channel.queue_bind(
            app.conf.PLATFORM_QUEUE_NAME, app.conf.result_exchange,
            routing_key='#')
        # Standard Exchange
        [p.maybe_declare(q) for q in app.conf.task_queues]
    finally:
        p.release()
