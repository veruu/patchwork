# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion

import re


# Django migrations don't allow us to call models' methods because the
# migration will break if the methods change. Therefore we need to use an
# altered copy of all the code needed.
def extract_tags(extract_from, tags):
    found_tags = {}

    if not extract_from.content:
        return found_tags

    for tag in tags:
        regex = re.compile(tag.pattern + r'\s(.*)', re.M | re.I)
        found_tags[tag] = regex.findall(extract_from.content)

    return found_tags


def add_tags(apps, submission, tag, values, comment=None):
    if not values:
        # We don't need to delete tags since none exist yet and we can't
        # delete comments etc. during the migration
        return

    if hasattr(submission, 'patch'):
        series = None
    else:
        series = submission.coverletter.series.first()

    SubmissionTag = apps.get_model('patchwork', 'SubmissionTag')
    current_objs = SubmissionTag.objects.filter(submission=self,
                                                comment=comment,
                                                tag=tag,
                                                series=series)

    # Only create nonexistent tags
    values_to_add = set(values) - set(current_objs.values_list('value',
                                                               flat=True))
    SubmissionTag.objects.bulk_create([SubmissionTag(
        submission=submission,
        tag=tag,
        value=value,
        comment=comment,
        series=series
    ) for value in values_to_add])


def create_all(apps, schema_editor):
    Tag = apps.get_model('patchwork', 'Tag')
    tags = Tag.objects.all()

    Submission = apps.get_model('patchwork', 'Submission')
    for submission in Submission.objects.all():
        extracted = extract_tags(submission, tags)
        for tag in extracted:
            add_tags(apps, submission, tag, extracted[tag])

    Comment = apps.get_model('patchwork', 'Comment')
    for comment in Comment.objects.all():
        extracted = extract_tags(comment, tags)
        for tag in extracted:
            add_tags(apps,
                     comment.submission,
                     tag,
                     extracted[tag],
                     comment=comment)


class Migration(migrations.Migration):

    dependencies = [
        ('patchwork', '0026_add_user_bundles_backref'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionTag',
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
                ('submission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Submission'
                )),
                ('tag', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Tag'
                )),
                ('series', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Series',
                    null=True
                )),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='patchtag',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='patchtag',
            name='patch',
        ),
        migrations.RemoveField(
            model_name='patchtag',
            name='tag',
        ),
        migrations.RemoveField(
            model_name='patch',
            name='tags',
        ),
        migrations.DeleteModel(
            name='PatchTag',
        ),
        migrations.AddField(
            model_name='submission',
            name='related_tags',
            field=models.ManyToManyField(
                through='patchwork.SubmissionTag',
                to='patchwork.Tag'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='submissiontag',
            unique_together=set([('submission',
                                  'tag',
                                  'value',
                                  'comment')]),
        ),
        migrations.RunPython(create_all, atomic=False),
    ]
