from celery import Celery


def add_worker_arguments(parser):
    parser.add_argument(
        '--msg-type', '-mt', default='task', choices=('task', 'result'),
        help='Message type.',
    ),


app = Celery()
app.conf.result_backend = 'tasks.backends:ResultQueueRPC'
app.config_from_object('django.conf:settings', namespace='CELERY')
app.user_options['worker'].add(add_worker_arguments)
