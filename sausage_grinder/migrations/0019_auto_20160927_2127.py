# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-28 02:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sausage_grinder', '0018_candidaterelease_has_single'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateartist',
            name='id',
            field=models.AutoField(auto_created=True, default=0, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='candidaterelease',
            name='id',
            field=models.AutoField(auto_created=True, default=0, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='candidatetrack',
            name='id',
            field=models.AutoField(auto_created=True, default=0, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='candidateartist',
            name='spotify_uri',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='candidaterelease',
            name='spotify_uri',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='candidatetrack',
            name='spotify_uri',
            field=models.CharField(default='', max_length=255),
        ),
    ]
