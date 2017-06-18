import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Consumer, Queue
from kombu.async import Hub

from tasks.celery import app
from tasks.consumer import ConsumeMessage


logger = logging.getLogger(__name__)
hub = Hub()


class Command(BaseCommand):
    help = "Sync task and result messages with database."

    def add_arguments(self, parser):
        parser.add_argument('--queue', '-q', default=settings.PLATFORM_QUEUE)

    def handle(self, queue, *args, **options):
        # fmt = '%(asctime)s %(name)-12s: %(levelname)-8s %(threadName)s %(message)s'
        # logging.basicConfig(level=logging.DEBUG,
        #                 format=fmt,
        #                 filename='./log',
        #                 filemode='a')
        # # Set up some logger to write console
        # console = logging.StreamHandler()
        # console.setLevel(logging.INFO)
        # formatter = logging.Formatter(fmt)
        # console.setFormatter(formatter)
        # logging.addHandler(console)
        with app.connection() as conn:
            conn.register_with_event_loop(hub)

            try:
                logger.info("Starting")
                with Consumer(conn, [Queue(queue)], on_message=ConsumeMessage):
                    hub.run_forever()
            except KeyboardInterrupt:
                logger.info("\nExiting...")
