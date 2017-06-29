# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-29 11:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_last_t'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicaluser',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='email address'),
        ),
        migrations.AlterField(
            model_name='historicaluser',
            name='phone',
            field=models.CharField(blank=True, max_length=16, null=True, verbose_name='phone number'),
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='email address'),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=16, null=True, verbose_name='phone number'),
        ),
    ]
