# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-08-24 03:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spotify_helper', '0002_auto_20160820_1653'),
    ]

    operations = [
        migrations.AddField(
            model_name='spotifyuser',
            name='return_path',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='spotifyuser',
            name='spotify_token',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='spotifyuser',
            name='spotify_username',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
