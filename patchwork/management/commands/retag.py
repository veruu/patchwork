# Patchwork - automated patch tracking system
# Copyright (C) 2015 Jeremy Kerr <jk@ozlabs.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.core.management.base import BaseCommand

from patchwork.models import Submission
from patchwork.parser import create_tags, extract_tags


class Command(BaseCommand):
    help = 'Update tags on existing submissions and associated comments'
    args = '[<submission_id>...]'

    def handle(self, *args, **options):
        query = Submission.objects.prefetch_related('comments')

        if args:
            query = query.filter(id__in=args)
        else:
            query = query.all()

        count = query.count()

        for i, submission in enumerate(query.iterator()):
            new_tags = extract_tags(submission.content,
                                    submission.project.tags)
            if hasattr(submission, 'patch'):
                create_tags(new_tags, submission.patch.series,
                            patch=submission.patch)
            else:
                create_tags(new_tags, submission.coverletter.series)

            for comment in submission.comments.all():
                comment_tags = extract_tags(comment.content,
                                            submission.project.tags)
                if hasattr(submission, 'patch'):
                    create_tags(new_tags, submission.patch.series,
                                patch=submission.patch, comment=comment)
                else:
                    create_tags(new_tags, submission.coverletter.series,
                                comment=comment)

            if (i % 10) == 0:
                self.stdout.write('%06d/%06d\r' % (i, count), ending='')
                self.stdout.flush()
        self.stdout.write('\ndone')
