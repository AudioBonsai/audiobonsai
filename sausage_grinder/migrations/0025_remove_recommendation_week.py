# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-10-28 17:25
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sausage_grinder', '0024_auto_20161028_1222'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recommendation',
            name='week',
        ),
    ]
