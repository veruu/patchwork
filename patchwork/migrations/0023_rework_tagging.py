# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

import re


# Django migrations don't allow us to call models' methods because the
# migration will break if the methods change. Therefore we can't use the
# overriden submission.save() and need to use an altered copy of all the
# code needed.

def extract_tags(content, tags):
    found_tags = {}
    for tag in tags:
        regex = re.compile(tag.pattern + '\s(.*)',
                           re.MULTILINE | re.IGNORECASE)
        found_tags[tag.name] = regex.findall(content)

    return found_tags


def _set_tag_values(apps, submission, tag, value_list):
    if not value_list:
        # We don't need to delete tags since none exist yet and we can't
        # delete comments etc. during the migration
        return

    SubmissionTag = apps.get_model('patchwork', 'SubmissionTag')
    submissiontag, _ = SubmissionTag.objects.get_or_create(
        submission=submission,
        tag=tag
    )
    TagValue = apps.get_model('patchwork', 'TagValue')
    for new_value in set(value_list):
        new, _ = TagValue.objects.get_or_create(value=new_value)
        submissiontag.values.add(new)
    submissiontag.count = len(set(value_list))
    submissiontag.save()


def create_key_value_tags(apps, submission):
    if not submission.project.use_tags:
        return
    Tag = apps.get_model('patchwork', 'Tag')
    tags = Tag.objects.all()

    if submission.content:
        submission_tags = extract_tags(submission.content, tags)
    else:
        submission_tags = {tag.name: [] for tag in tags}

    submission_comment_tags = extract_tags(
        '\n'.join([comment.content for comment in submission.comments.all()]),
        tags
    )
    for tag in tags:
        submission_tags[tag.name].extend(submission_comment_tags[tag.name])

    SeriesReference = apps.get_model('patchwork', 'SeriesReference')
    related_series = None
    refs = [hdr.split(': ')[1] for hdr in submission.headers.split('\n') if
            hdr.split(': ')[0] == 'In-Reply-To' or
            hdr.split(': ')[0] == 'References'] + [submission.msgid]
    for ref in refs:
        try:
            related_series = SeriesReference.objects.get(
                msgid=ref,
                series__project=submission.project
            ).series
        except SeriesReference.DoesNotExist:
            continue

    if related_series:
        if hasattr(submission, 'coverletter'):
            for patch in related_series.patches.all():
                merged_content = '\n'.join([comment.content for comment in
                                            patch.comments.all()])
                if patch.content:
                    merged_content += '\n' + patch.content

                added_tags = extract_tags(merged_content, tags)

                for tag in tags:
                    _set_tag_values(
                        apps,
                        patch,
                        tag,
                        submission_tags[tag.name] + added_tags[tag.name]
                    )
        else:
            cover = related_series.cover_letter
            if cover:
                cover_tags = extract_tags(
                    '\n'.join([comment.content for comment in
                               cover.comments.all()] + [cover.content]),
                    tags
                )
                for tag in tags:
                    submission_tags[tag.name].extend(cover_tags[tag.name])

    for tag in tags:
        _set_tag_values(apps, submission, tag, submission_tags[tag.name])


def call_all(apps, schema_editor):
    Series = apps.get_model('patchwork', 'Series')
    # Split the patches into groups (with a cover letter and without it).
    # Avoid calling the function multiple times for the same patch in case
    # there is a cover letter associated.
    for series in Series.objects.filter(cover_letter__isnull=False):
        create_key_value_tags(apps, series.cover_letter)
    for series in Series.objects.filter(cover_letter__isnull=True):
        for patch in series.patches.all():
            create_key_value_tags(apps, patch)


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
        migrations.AlterUniqueTogether(
            name='SubmissionTag',
            unique_together=set([('submission', 'tag')]),
        ),
        migrations.CreateModel(
            name='TagValue',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('value', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='submissiontag',
            name='values',
            field=models.ManyToManyField(to='patchwork.TagValue'),
        ),
        migrations.RunPython(call_all, atomic=False),
    ]
