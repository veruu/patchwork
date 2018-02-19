# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Counter
from django.db import connection, migrations, models

import re


# Django migrations don't allow us to call models' methods because the
# migration will break if the methods change. Therefore we can't use the
# overriden submission.save() that extracts and creates all the SubmissionTags
# and need to copy altered version of all the code needed here.
def extract_tags(content, tags):
    counts = Counter()
    for tag in tags:
        regex = re.compile(tag.pattern, re.MULTILINE | re.IGNORECASE)
        counts[tag] = len(regex.findall(content))
    return counts


def set_tag(apps, submission, tag, count):
    if not count:
        # We don't need to delete tags since none exist yet and we can't
        # delete comments etc. during this migration
        return
    SubmissionTag = apps.get_model('patchwork', 'SubmissionTag')
    submissiontag, _ = SubmissionTag.objects.get_or_create(
        submission=submission,
        tag=tag
    )
    if submissiontag.count != count:
        submissiontag.count = count
        submissiontag.save()


def refresh_tag_counts(apps, submission):
    if not submission.project.use_tags:
        return
    Tag = apps.get_model('patchwork', 'Tag')
    tags = Tag.objects.all()
    counter = Counter()

    if submission.content:
        counter += extract_tags(submission.content, tags)
    for comment in submission.comments.all():
        counter = counter + extract_tags(comment.content, tags)

    SeriesReference = apps.get_model('patchwork', 'SeriesReference')
    related_series = None
    refs = [hdr.split(': ')[1] for hdr in submission.headers.split('\n') if
            hdr.split(': ')[0] == 'In-Reply-To' or
            hdr.split(': ')[0] == 'References'] + [submission.msgid]
    for ref in refs:
        try:
            related_series = SeriesReference.objects.get(
                msgid=submission.msgid,
                series__project=submission.project
            ).series
        except SeriesReference.DoesNotExist:
            continue

    if related_series:
        if hasattr(submission, 'coverletter'):
            for patch in related_series.patches.all():
                patch_counter = counter

                if patch.content:
                    patch_counter += extract_tags(patch.content, tags)
                for comment in patch.comments.all():
                    patch_counter += extract_tags(comment.content, tags)

                for tag in tags:
                    set_tag(apps, patch, tag, patch_counter[tag])
        else:
            cover = related_series.cover_letter
            if cover:
                counter += extract_tags(cover.content, tags)
                for comment in cover.comments.all():
                    counter += extract_tags(comment.content, tags)

    for tag in tags:
        set_tag(apps, submission, tag, counter[tag])


def create_new_tags(apps, schema_editor):
    Series = apps.get_model('patchwork', 'Series')
    for series in Series.objects.filter(cover_letter__isnull=False):
        refresh_tag_counts(apps, series.cover_letter)


class Migration(migrations.Migration):

    dependencies = [
        ('patchwork', '0022_add_subject_match_to_project'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='PatchTag',
            new_name='SubmissionTag'
        ),
        migrations.RenameField(
            model_name='SubmissionTag',
            old_name='patch',
            new_name='submission'
        ),
        migrations.AlterField(
            model_name='SubmissionTag',
            name='submission',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE,
                                    to='patchwork.Submission')
        ),
        migrations.AddField(
            model_name='Submission',
            name='submission_tags',
            field=models.ManyToManyField(through='patchwork.SubmissionTag',
                                         to='patchwork.Tag')
        ),
        migrations.RunPython(create_new_tags, atomic=False),
        migrations.AlterUniqueTogether(
            name='SubmissionTag',
            unique_together=set([('submission', 'tag')]),
        )
    ]
