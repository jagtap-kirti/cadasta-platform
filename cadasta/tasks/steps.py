import logging
import time

from celery import bootsteps
from django.conf import settings
from django.db.models import F
from django.db.models.expressions import CombinedExpression, Value
from kombu import Consumer, Queue


logger = logging.getLogger(__name__)


class DisableQueues(bootsteps.StartStopStep):

    def create(self, worker):
        logger.info('Disabling queues')
        worker.app.amqp.queues = {}
        # TODO: Without any known queues, the worker processes a default
        # queue (celery), creating it if it does not exist. Is there a
        # way to start the worker via `$ celery worker` but only run the
        # consumers?
        return self

    def start(self, worker):
        pass

    def stop(self, worker):
        pass

    def terminate(self, worker):
        pass


class MessageConsumer(bootsteps.ConsumerStep):
    """
    Reads off the Task Duplicate queue and Result queue, inserting
    messages into DB. NOTE: This only works if you run a celery worker
    that is NOT looking at the Result queue. Ex. "celery -A config worker"
    """
    # def __init__(self, parent, msg_type, *args, **kwargs):
    #     self.msg_type = msg_type

    def get_consumers(self, channel):
        return [Consumer(
            channel,
            queues=[Queue(settings.PLATFORM_QUEUE)],
            callbacks=[self.handle_message],
            accept=['json'])]

    def handle_message(self, body, message):
        try:
            try:
                handler = self._detect_msg_type(message)
            except TypeError:
                logger.exception("Unknown message type:\n%r", message)
                raise
            try:
                return handler(body, message)
            except:
                logger.exception("Failed to process message:\n%r", message)
                raise
        finally:
            message.ack()

    def _detect_msg_type(self, message):
        if 'task' in message.headers:
            return self._handle_task
        if 'result' in message.payload:
            return self._handle_result
        raise TypeError("Cannot detect message type")

    @staticmethod
    def _handle_task(body, message):
        from .models import BackgroundTask
        logger.debug("Handling task message %r", body)
        args, kwargs, options = message.decode()
        task_id = message.headers['id']

        # Add default properties
        option_keys = ['eta', 'expires', 'retries', 'timelimit']
        message.properties.update(
            **{k: v for k, v in message.headers.items()
               if k in option_keys and v not in (None, [None, None])})

        # Ensure chained followup tasks contain proper data
        chain_parent_id = task_id[:]
        chain = options.get('chain') or []
        for t in chain[::-1]:  # Chain array comes in reverse order
            t['parent_id'] = chain_parent_id
            chain_parent_id = t['options']['task_id']

        # TODO: Add support for grouped tasks
        # TODO: Add support tasks gednerated by workers
        _, created = BackgroundTask.objects.get_or_create(
            id=task_id,
            defaults={
                'type': message.headers['task'],
                'input_args': args,
                'input_kwargs': kwargs,
                'options': message.properties,
                'parent_id': message.headers['parent_id'],
                'root_id': message.headers['root_id'],
            }
        )
        if created:
            logger.debug("Processed task: %r", message)
        else:
            logger.warn("Task already existed in db: %r", message)



    @staticmethod
    def _handle_result(body, message):
        from .models import BackgroundTask
        logger.debug("Handling result message %r", body)
        result = message.payload
        logger.debug('Received message: %r', result)
        task_id = result['task_id']
        task_qs = BackgroundTask.objects.filter(id=task_id)

        MAX_TIME = 5
        start = time.time()
        while not task_qs.exists():
            logger.debug("No corresponding task found (%r), retrying...", task_id)
            if (time.time() - start) > MAX_TIME:
                logger.exception("No corresponding task found. Giving up.")
                return
            time.sleep(.25)

        status = result.get('status')
        if status:
            task_qs.update(status=status)

        result = result['result']
        if status in BackgroundTask.DONE_STATES:
            task_qs.update(output=result)
        else:
            assert isinstance(result, dict), (
                "Malformed result data, expecting a dict"
            )
            log = result.get('log')
            if log:
                task_qs.update(log=CombinedExpression(
                    F('log'), '||', Value([log])
                ))
