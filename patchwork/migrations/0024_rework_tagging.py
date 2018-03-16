# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import migrations, models
import django.db.models.deletion

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


def _set_tag_values(apps, tag_related_to, tag, value_list):
    if not value_list:
        # We don't need to delete tags since none exist yet and we can't
        # delete comments etc. during the migration
        return

    RelatedTag = apps.get_model('patchwork', 'RelatedTag')
    obj_type = ContentType.objects.get_for_model(tag_related_to)
    relatedtag, _ = RelatedTag.objects.get_or_create(
        content_type=obj_type,
        object_id=tag_related_to.id,
        tag=tag
    )
    TagValue = apps.get_model('patchwork', 'TagValue')
    for new_value in set(value_list):
        new, _ = TagValue.objects.get_or_create(value=new_value)
        relatedtag.values.add(new)
    relatedtag.save()


def create_key_value_tags(apps, tags_related_to):
    if hasattr(tag_related_to, 'project'):
        tags = tags = self.project.tags
    else:
        tags = self.submission.project.tags

    if tags_related_to.content:
        related_to_tags = extract_tags(tags_related_to.content, tags)
        for tag in tags:
            _set_tag_values(apps,
                            tags_related_to,
                            tag,
                            related_to_tags[tag.name])


def call_all(apps, schema_editor):
    Submission = apps.get_model('patchwork', 'Submission')
    for submission in Submission.objects.all():
        create_key_value_tags(apps, submission)
    Comment = apps.get_model('patchwork', 'Comment')
    for comment in Comment.objects.all():
        create_key_value_tags(apps, comment)


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('patchwork', '0023_timezone_unify'),
    ]

    operations = [
        migrations.CreateModel(
            name='RelatedTag',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.ContentType'
                )),
                ('tag', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='patchwork.Tag'
                )),
            ],
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
            model_name='relatedtag',
            name='values',
            field=models.ManyToManyField(to='patchwork.TagValue'),
        ),
        migrations.AlterUniqueTogether(
            name='relatedtag',
            unique_together=set([('content_type',
                                  'object_id',
                                  'tag')]),
        ),
        # FIXME do we need to add related_to to submission and comment?
        migrations.RunPython(call_all, atomic=False),
    ]
