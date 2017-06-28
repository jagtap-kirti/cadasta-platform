from collections import namedtuple
from unittest.mock import patch, MagicMock, call

from django.test import TestCase, override_settings
from django.db.models import F
from django.db.models.expressions import CombinedExpression, Value

from tasks.consumer import Worker
from tasks.tests.factories import BackgroundTaskFactory


@override_settings(CELERY_RESULT_QUEUE='results-queue')
class TestConsumers(TestCase):

    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_queues = MagicMock()
        self.mock_worker = Worker(
            connection=self.mock_conn, queues=self.mock_queues)

    def test_get_queues(self):
        MockConsumer = namedtuple('Consumer', 'queues,accept,callbacks')
        MockQueue = namedtuple('Queue', 'name')
        mock_channel = MagicMock()
        w = Worker(
            connection=self.mock_conn,
            queues=[MockQueue(name='foobar')]
        )
        consumers = w.get_consumers(MockConsumer, mock_channel)

        self.assertEqual(len(consumers), 1)
        consumer = consumers[0]
        self.assertEqual(len(consumer.queues), 1)
        queue = consumer.queues[0]
        self.assertEqual(queue.name, 'foobar')

        self.assertEqual(len(consumer.callbacks), 1)
        self.assertEqual(consumer.callbacks[0], w.process_task)

    @patch('tasks.consumer.Worker._detect_msg_type')
    def test_process_task_routes_messages_to_handler(self, detect_msg):
        """
        Ensure that process_task() calls a handler if message type is
        detected
        """
        handler = MagicMock()
        detect_msg.return_value = handler
        body = MagicMock()
        msg = MagicMock()
        self.mock_worker.process_task(body, msg)
        handler.assert_called_once_with(body, msg)
        msg.ack.assert_called_once_with()

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.Worker._detect_msg_type')
    def test_process_task_handles_unknown_message(self, detect_msg, logger):
        """
        Ensure that process_task() gracefully handles unknown messages
        """
        detect_msg.side_effect = TypeError()  # Unable to detect task type
        body = MagicMock()
        msg = MagicMock()
        self.mock_worker.process_task(body, msg)
        # import pytest; pytest.set_trace()
        self.assertEqual(logger.exception.call_count, 1)
        msg.ack.assert_called_once_with()

    @patch('tasks.consumer.BackgroundTask.objects.filter')
    def test_handle_result_completed(self, mock_filter):
        """
        Ensure completed tasks set output to the output property.
        """
        mock_qs = MagicMock()
        mock_filter.return_value = mock_qs

        mock_body = MagicMock()
        mock_msg = MagicMock(payload={
            'task_id': '123',
            'status': 'SUCCESS',
            'result': 'All succeeded',
        })
        Worker(
            connection=self.mock_conn,
            queues=self.mock_queues
        )._handle_result(mock_body, mock_msg)
        mock_qs.update.assert_has_calls([
            call(status='SUCCESS'),
            call(output='All succeeded')
        ])

    # # @patch('tasks.consumer.bootsteps.ConsumerStep.__init__', MagicMock())
    # @patch('tasks.consumer.BackgroundTask.objects.filter')
    # def test_handle_result_in_progress_dict_log(self, mock_filter):
    #     """
    #     Ensure in-progess tasks append output dict with log key to the log.
    #     """
    #     mock_qs = MagicMock()
    #     mock_filter.return_value = mock_qs

    #     mock_msg = MagicMock(payload={
    #         'task_id': '123',
    #         'status': 'PROGRESS',
    #         'result': {'log': 'Things are coming along'},
    #     })
    #     fake_body = MagicMock()
    #     Worker(
    #         connection=self.mock_conn,
    #         queues=self.mock_queues
    #     )._handle_result(fake_body, mock_msg)
    #     calls = mock_qs.update.call_args_list
    #     self.assertEqual(calls[0], call(status='PROGRESS'))
    #     self.assertEqual(
    #         str(calls[1]),
    #         str(call(log=CombinedExpression(
    #             F('log'), '||', Value(['Things are coming along'])
    #         )))
    #     )
    #     mock_msg.ack.assert_called_once_with()

    # # @patch('tasks.consumer.bootsteps.ConsumerStep.__init__', MagicMock())
    # @patch('tasks.consumer.logger')
    # def test_handle_result_handles_exceptions(self, mock_log):
    #     """
    #     Ensure that exceptions in task parsing are handled gracefully
    #     """
    #     mock_msg = MagicMock()
    #     empty_body = {}
    #     Worker(
    #         connection=self.mock_conn,
    #         queues=self.mock_queues
    #     )._handle_result(MagicMock(), mock_msg)
    #     mock_msg.ack.assert_called_once_with()
    #     self.assertEqual(mock_log.exception.call_count, 1)

    # # @patch('tasks.consumer.bootsteps.ConsumerStep.__init__', MagicMock())
    # @patch('tasks.consumer.BackgroundTask.objects.filter')
    # @patch('tasks.consumer.logger')
    # def test_handle_result_handles_failed_ack(self, mock_log, mock_filter):
    #     """
    #     Ensure that exceptions in task parsing are handled gracefully
    #     """
    #     task = BackgroundTaskFactory.build(status='PENDING')
    #     mock_filter.exists.return_value = True
    #     task.save = MagicMock()
    #     mock_msg = MagicMock(payload={
    #         'task_id': '123',
    #         'status': 'PROGRESS',
    #         'result': {'log': 'Things are coming along'},
    #     })
    #     ack_func = MagicMock(side_effect=Exception("Failed ack"))
    #     mock_msg = MagicMock(ack=ack_func)
    #     Worker(
    #         connection=self.mock_conn,
    #         queues=self.mock_queues
    #     )._handle_result(MagicMock(), mock_msg)
    #     ack_func.assert_called_once_with()
    #     self.assertEqual(mock_log.exception.call_count, 1)
