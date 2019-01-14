# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


# Only add the model field. Since the cover letter should arrive within approx.
# 10 mins form the patches (delayed emails happen), we actually don't expect to
# wait for any old emails. They should be already there.
class Migration(migrations.Migration):

    dependencies = [
        ('patchwork', '0033_remove_patch_series_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='series',
            name='cover_expected',
            field=models.BooleanField(default=False),
        ),
    ]
