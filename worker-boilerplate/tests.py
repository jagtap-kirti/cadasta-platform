import unittest

from celery import signals

from app.celery import app


class TestExchangeConfiguration(unittest.TestCase):

    def setUp(self):
        signals.worker_init.send(sender=None)
        self.channel = app.connection().channel()

    def test_default_exchange_type(self):
        """ Ensure default exchange is topic exchange """
        exch_type = self.channel.typeof(app.conf.task_default_exchange).type
        self.assertEqual(exch_type, 'topic')

    def test_result_exchange_details(self):
        """ Ensure result exchange is topic exchange """
        exchange = self.channel.state.exchanges[app.conf.result_exchange]
        self.assertEqual(exchange, {
            'type': 'topic',
            'auto_delete': False,
            'table': [('#', '^.*?$', 'platform.fifo')],
            'durable': True,
            'arguments': {}
        })

    def test_default_exchange_routing(self):
        """ Ensure default exchange routes tasks to multiple queues """
        exchange = app.conf.task_default_exchange
        queues = self.channel.typeof(exchange).lookup(
            self.channel.get_table(exchange),
            exchange, 'export', app.conf.task_default_queue)
        self.assertEqual(len(queues), 2)

    def test_result_exchange_routing(self):
        """ Ensure result exchange routes tasks to multiple queues """
        exchange = app.conf.result_exchange
        self.channel.queue_bind(
            'foo', exchange, routing_key='foo')
        queues = self.channel.typeof(exchange).lookup(
            self.channel.get_table(exchange),
            exchange, 'foo', app.conf.task_default_queue)
        self.assertEqual(len(queues), 2)


if __name__ == '__main__':
    unittest.main()
