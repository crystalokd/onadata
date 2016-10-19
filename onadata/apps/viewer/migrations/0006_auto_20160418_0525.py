# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-18 09:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0005_auto_20160408_0325'),
    ]

    operations = [
        migrations.AlterField(
            model_name='export',
            name='export_type',
            field=models.CharField(choices=[(b'xls', b'Excel'), (b'csv', b'CSV'), (b'zip', b'ZIP'), (b'kml', b'kml'), (b'csv_zip', b'CSV ZIP'), (b'sav_zip', b'SAV ZIP'), (b'sav', b'SAV'), (b'external', b'Excel'), ('osm', 'osm'), (b'gsheets', b'Google Sheets')], default=b'xls', max_length=10),
        ),
    ]