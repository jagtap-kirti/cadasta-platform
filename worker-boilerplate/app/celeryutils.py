from celery import Task as _Task
from celery.backends.rpc import RPCBackend


class Task(_Task):
    def log(self, msg):
        """ Helper to compose log messages """
        return self.update_state(meta={'log': msg}, request=self.request)

    def update_state(self, task_id=None, state=None, meta=None, **kwargs):
        """Update task state.
        Overridden from default to allow for kwargs to pass through to
        self.backend.store_result

        Arguments:
            task_id (str): Id of the task to update.
                Defaults to the id of the current task.
            state (str): New state.
            meta (Dict): State meta-data.
        """
        if task_id is None:
            task_id = self.request.id
        self.backend.store_result(task_id, meta, state, **kwargs)


class ResultQueueRPC(RPCBackend):

    def _create_exchange(self, name, type='topic', delivery_mode=2):
        # Use app's provided exchange information rather than a RPCBackend's
        # default of an unnamed direct exchange
        return self.Exchange(name=name, type=type, delivery_mode=delivery_mode)

    def store_result(self, *args, **kwargs):
        """
        Ensure that 'reply_to' queue is registered with exchange, so
        that results are routed to both 'reply_to' queue and platform
        queue.
        """
        request = kwargs['request']
        reply_to = request.reply_to
        if reply_to:
            with self.app.pool.acquire_channel(block=True) as (_, channel):
                channel.queue_bind(
                    reply_to, self.exchange.name, routing_key=reply_to)
        return super(ResultQueueRPC, self).store_result(*args, **kwargs)
