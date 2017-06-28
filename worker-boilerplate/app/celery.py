from __future__ import absolute_import

from celery import Celery
from .signals import *  # NOQA


app = Celery('app',
             task_cls='app.celeryutils.Task',
             backend='app.celeryutils.ResultQueueRPC',)
app.config_from_object('app.celeryconfig')
