# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-25 03:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spotify_helper', '0003_auto_20160823_2207'),
    ]

    operations = [
        migrations.AlterField(
            model_name='spotifyuser',
            name='spotify_token',
            field=models.TextField(blank=True, default=''),
        ),
    ]
