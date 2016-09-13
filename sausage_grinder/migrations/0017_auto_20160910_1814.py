# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-09-10 23:14
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
import django.db.models.deletion
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('sausage_grinder', '0016_auto_20160909_0752'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateartist',
            name='week',
            #field=models.ForeignKey(default=datetime.datetime(2016, 9, 10, 23, 14, 39, 27522, tzinfo=utc), on_delete=django.db.models.deletion.CASCADE, to='sausage_grinder.CandidateSet'),
            field=models.ForeignKey(default=0,
                                    on_delete=django.db.models.deletion.CASCADE, to='sausage_grinder.CandidateSet'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='genre',
            name='week',
            #field=models.ForeignKey(default=datetime.datetime(2016, 9, 10, 23, 14, 45, 603883, tzinfo=utc), on_delete=django.db.models.deletion.CASCADE, to='sausage_grinder.CandidateSet'),
            field=models.ForeignKey(default=0,
                                    on_delete=django.db.models.deletion.CASCADE, to='sausage_grinder.CandidateSet'),
            preserve_default=False,
        ),
    ]
