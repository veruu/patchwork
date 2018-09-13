# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patchwork', '0033_remove_patch_series_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeriesTag',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('comment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Comment',
                    null=True
                )),
                ('patch', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Patch',
                    null=True
                )),
                ('tag', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Tag'
                )),
                ('series', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Series',
                )),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='patchtag',
            unique_together=set([]),
        ),
        migrations.RemoveField(model_name='patchtag', name='patch',),
        migrations.RemoveField(model_name='patchtag', name='tag',),
        migrations.RemoveField(model_name='patch', name='tags',),
        migrations.DeleteModel(name='PatchTag',),
        migrations.AddField(
            model_name='series',
            name='tags',
            field=models.ManyToManyField(
                through='patchwork.SeriesTag',
                to='patchwork.Tag'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='seriestag',
            unique_together=set([('patch',
                                  'tag',
                                  'value',
                                  'comment')]),
        ),
    ]
