# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-28 11:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_user_foreign_key'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='verificationdevice',
            name='last_t',
        ),
        migrations.AddField(
            model_name='verificationdevice',
            name='last_verified_counter',
            field=models.BigIntegerField(default=-1, help_text='The counter value of the latest verified token.         The next token must be at a higher counter value.         It makes sure a token is used only once.'),
        ),
    ]
