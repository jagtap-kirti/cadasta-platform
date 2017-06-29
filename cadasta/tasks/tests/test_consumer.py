from collections import namedtuple
from unittest.mock import patch, MagicMock, call

from django.test import TestCase, override_settings
from django.db.models import F
from django.db.models.expressions import CombinedExpression, Value

from tasks.consumer import Worker
from tasks.tests.factories import BackgroundTaskFactory


class TestConsumers(TestCase):

    def setUp(self):
        self.mock_conn = MagicMock(as_uri=MagicMock(return_value='sqs://'))
        self.mock_queues = MagicMock()
        self.mock_worker = Worker(
            connection=self.mock_conn, queues=self.mock_queues)

    def get_result_msg(self):
        args, kwargs = [], {}
        return MagicMock(
            headers={},
            payload={
                'status': None,
                'children': [],
                'result': {'log': 'About to download some huge file'},
                'traceback': None,
                'task_id': '486e8738-a9ef-475a-b8e1-158e987f4ae6'
            },
            decode=MagicMock(return_value=(args, kwargs, {})),
            properties={}
        )

    def get_task_msg(self, chain=None):
        args, kwargs = [], {}
        headers = {
            'kwargsrepr': '{}',
            'retries': 0,
            'eta': None,
            'timelimit': [None, None],
            'task': 'export.hello',
            'expires': None,
            'origin': 'gen4340@vagrant-ubuntu-trusty-64',
            'parent_id': None,
            'group': None,
            'lang': 'py',
            'root_id': '486e8738-a9ef-475a-b8e1-158e987f4ae6',
            'argsrepr': '()',
            'id': '486e8738-a9ef-475a-b8e1-158e987f4ae6'
        }
        return MagicMock(
            headers=headers,
            payload=[
                args, kwargs,
                {'callbacks': None, 'chain': chain,
                 'errbacks': None, 'chord': None}
            ],
            decode=MagicMock(return_value=(args, kwargs, headers)),
            properties={}
        )

    @staticmethod
    def assert_sqs_ack(sqs_client, msg):
        return sqs_client.delete_message.assert_called_once_with(
            QueueUrl=msg.delivery_info['sqs_queue'],
            ReceiptHandle=msg.delivery_info['sqs_message']['ReceiptHandle']
        )

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
    @patch('tasks.consumer.boto3.client')
    def test_process_task_routes_messages_to_handler(
            self, boto3_client, detect_msg):
        """
        Ensure that process_task() calls a handler if message type is
        detected
        """
        handler = MagicMock()
        detect_msg.return_value = handler
        body = MagicMock()
        msg = MagicMock()
        sqs_client = MagicMock()
        boto3_client.return_value = sqs_client

        self.mock_worker.process_task(body, msg)

        handler.assert_called_once_with(body, msg)
        self.assert_sqs_ack(sqs_client, msg)

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.Worker._detect_msg_type')
    @patch('tasks.consumer.boto3.client')
    def test_process_task_handles_unknown_message(
            self, boto3_client, detect_msg, logger):
        """
        Ensure that process_task() gracefully handles unknown messages
        """
        detect_msg.side_effect = TypeError()  # Unable to detect task type
        body = MagicMock()
        msg = MagicMock()
        sqs_client = MagicMock()
        boto3_client.return_value = sqs_client

        self.mock_worker.process_task(body, msg)

        self.assertEqual(logger.exception.call_count, 1)
        self.assert_sqs_ack(sqs_client, msg)
        logger.exception.assert_called_once_with(
            'Unknown message type: %r', msg)

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.Worker._detect_msg_type')
    @patch('tasks.consumer.boto3.client')
    def test_process_task_handles_failed_parsing(
            self, boto3_client, detect_msg, logger):
        """
        Ensure that process_task() gracefully handles message parsing failures
        """
        handler = MagicMock(side_effect=Exception())
        detect_msg.return_value = handler
        body = MagicMock()
        msg = MagicMock()
        sqs_client = MagicMock()
        boto3_client.return_value = sqs_client

        self.mock_worker.process_task(body, msg)

        self.assertEqual(logger.exception.call_count, 1)
        self.assert_sqs_ack(sqs_client, msg)
        logger.exception.assert_called_once_with(
            'Failed to process message: %r', msg)

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.Worker._detect_msg_type')
    def test_non_sqs_ack(self, detect_msg, logger):
        """
        Ensure that non-sqs connections correctly ack messages
        """
        handler = MagicMock()
        detect_msg.return_value = handler
        msg = MagicMock()
        self.mock_worker.connection.as_uri = MagicMock(return_value='amqp://')

        self.mock_worker.process_task(MagicMock(), msg)

        msg.ack.assert_called_once_with()
        self.assertEqual(logger.exception.call_count, 0)

    @patch('tasks.consumer.BackgroundTask.objects.filter')
    def test_handle_result_completed(self, mock_filter):
        """
        Ensure completed tasks set output to the output property
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

    def test_detect_task_msg(self):
        """ Ensure worker properly detects task messages """
        handler = self.mock_worker._detect_msg_type(self.get_task_msg())
        self.assertEqual(handler, self.mock_worker._handle_task)

    def test_detect_result_msg(self):
        """ Ensure worker properly detects result messages """
        handler = self.mock_worker._detect_msg_type(self.get_result_msg())
        self.assertEqual(handler, self.mock_worker._handle_result)

    def test_handles_unknown_result_msg(self):
        """ Ensure worker throws TypeError on unknown message type """
        with self.assertRaises(TypeError):
            self.mock_worker._detect_msg_type(MagicMock())

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.BackgroundTask')
    def test_handle_new_task(self, BackgroundTask, logger):
        body = MagicMock()
        msg = self.get_task_msg()
        BackgroundTask.objects.get_or_create.return_value = (None, True)

        self.mock_worker._handle_task(body, msg)

        BackgroundTask.objects.get_or_create.assert_called_once_with(
            defaults={
                'type': 'export.hello',
                'root_id': '486e8738-a9ef-475a-b8e1-158e987f4ae6',
                'input_kwargs': {},
                'input_args': [],
                'options': {'retries': 0},
                'parent_id': None
            },
            id='486e8738-a9ef-475a-b8e1-158e987f4ae6'
        )
        self.assertEqual(logger.debug.call_args_list, [
            call('Handling task message %r', body),
            call('Processed task: %r', msg)])

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.BackgroundTask')
    def test_handle_existing_task(self, BackgroundTask, logger):
        """
        Ensure handle_task logs already existing task as warning.
        """
        body = MagicMock()
        msg = self.get_task_msg()
        BackgroundTask.objects.get_or_create.return_value = (None, False)

        self.mock_worker._handle_task(body, msg)

        BackgroundTask.objects.get_or_create.assert_called_once_with(
            defaults={
                'type': 'export.hello',
                'root_id': '486e8738-a9ef-475a-b8e1-158e987f4ae6',
                'input_kwargs': {},
                'input_args': [],
                'options': {'retries': 0},
                'parent_id': None
            },
            id='486e8738-a9ef-475a-b8e1-158e987f4ae6'
        )
        logger.debug.assert_called_once_with(
            'Handling task message %r', body)
        logger.warn.assert_called_once_with(
            "Task already existed in db: %r", msg)

    @patch('tasks.consumer.BackgroundTask.objects.filter')
    def test_handle_result_in_progress_dict_log(self, mock_filter):
        """
        Ensure handle_result appends data from output dict with log key to the
        task's log field.
        """
        mock_qs = MagicMock()
        mock_filter.return_value = mock_qs

        mock_msg = self.get_result_msg()
        fake_body = MagicMock()

        Worker(
            connection=self.mock_conn,
            queues=self.mock_queues
        )._handle_result(fake_body, mock_msg)

        self.assertEqual(mock_qs.update.call_count, 1)
        expected_call = call(log=CombinedExpression(
            F('log'), '||', Value(['About to download some huge file'])
        ))
        self.assertEqual(
            str(mock_qs.update.call_args_list[0]),
            str(expected_call)
        )

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.BackgroundTask.objects.filter')
    def test_handle_result_malformed(self, mock_filter, logger):
        """
        Ensure handle_result properly logs malformed result data.
        """
        mock_qs = MagicMock()
        mock_filter.return_value = mock_qs

        mock_msg = self.get_result_msg()
        mock_msg.payload['result'] = "This is malformed..."
        fake_body = MagicMock()

        Worker(
            connection=self.mock_conn,
            queues=self.mock_queues
        )._handle_result(fake_body, mock_msg)

        logger.error.assert_called_once_with(
            "Malformed result data, expecting a dict, got %s (%r)", str,
            mock_msg.payload['result']
        )

    @patch('tasks.consumer.logger')
    @patch('tasks.consumer.BackgroundTask.objects.filter')
    def test_handle_result_does_not_exist(self, mock_filter, logger):
        """
        Ensure handle_result properly logs result for non-existant task.
        """
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_filter.return_value = mock_qs

        mock_msg = self.get_result_msg()
        fake_body = MagicMock()

        Worker(
            connection=self.mock_conn,
            queues=self.mock_queues
        )._handle_result(fake_body, mock_msg)

        logger.error.assert_called_once_with(
            "No corresponding task found (%r)", mock_msg.payload['task_id']
        )
