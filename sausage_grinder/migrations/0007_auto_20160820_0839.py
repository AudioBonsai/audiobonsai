# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-08-20 13:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sausage_grinder', '0006_auto_20160819_2051'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='candidaterelease',
            name='id',
        ),
        migrations.AddField(
            model_name='candidaterelease',
            name='batch',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='candidaterelease',
            name='spotify_uri',
            field=models.CharField(default='', max_length=255, primary_key=True, serialize=False),
        ),
    ]
