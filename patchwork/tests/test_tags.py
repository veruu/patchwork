# Patchwork - automated patch tracking system
# Copyright (C) 2014 Jeremy Kerr <jk@ozlabs.org>
#
# This file is part of the Patchwork package.
#
# Patchwork is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Patchwork is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Patchwork; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import mailbox
import os

from django.test import TestCase
from django.test import TransactionTestCase

from patchwork.models import Patch
from patchwork.models import Series
from patchwork.models import SeriesPatch
from patchwork.models import Submission
from patchwork.models import SubmissionTag
from patchwork.models import Tag
from patchwork.parser import parse_mail
from patchwork.tests import TEST_MAIL_DIR
from patchwork.tests.utils import create_comment
from patchwork.tests.utils import create_patch
from patchwork.tests.utils import create_project


class ExtractTagsTest(TestCase):

    fixtures = ['default_tags']
    email = 'test@example.com'
    name_email = 'test name <' + email + '>'

    def assertTagsEqual(self, str, acks, reviews, tests):  # noqa
        found_tags = Submission.extract_tags(str, Tag.objects.all())
        # Make sure we have the same elements, but we don't care about the
        # order if there are more values
        self.assertEqual((set(acks), set(reviews), set(tests)),
                         (set(found_tags['Acked-by']),
                          set(found_tags['Reviewed-by']),
                          set(found_tags['Tested-by'])))

    def test_empty(self):
        self.assertTagsEqual('', [], [], [])

    def test_no_tag(self):
        self.assertTagsEqual('foo', [], [], [])

    def test_ack(self):
        self.assertTagsEqual('Acked-by: %s' % self.name_email,
                             [self.name_email], [], [])

    def test_ack_email_only(self):
        self.assertTagsEqual('Acked-by: %s' % self.email,
                             [self.email], [], [])

    def test_reviewed(self):
        self.assertTagsEqual('Reviewed-by: %s' % self.name_email,
                             [], [self.name_email], [])

    def test_tested(self):
        self.assertTagsEqual('Tested-by: %s' % self.name_email,
                             [], [], [self.name_email])

    def test_ack_after_newline(self):
        self.assertTagsEqual('\nAcked-by: %s' % self.name_email,
                             [self.name_email], [], [])

    def test_multiple_acks_by_same_person(self):
        str = 'Acked-by: %s\nAcked-by: %s\n' % ((self.name_email,) * 2)
        self.assertTagsEqual(str, [self.name_email], [], [])

    def test_multiple_types_by_same_person(self):
        str = 'Acked-by: %s\nAcked-by: %s\nReviewed-by: %s\n' % (
            (self.name_email,) * 3)
        self.assertTagsEqual(str, [self.name_email], [self.name_email], [])

    def test_multiple_types_by_different_people(self):
        another = 'Another Person <name@surname.test>'
        str = 'Acked-by: %s\nAcked-by: %s\nReviewed-by: %s\n' % (
            self.name_email, another, self.name_email
        )
        self.assertTagsEqual(str,
                             [self.name_email, another],
                             [self.name_email],
                             [])

    def test_lower(self):
        self.assertTagsEqual('acked-by: %s' % self.name_email,
                             [self.name_email], [], [])

    def test_upper(self):
        self.assertTagsEqual('ACKED-BY: %s' % self.name_email,
                             [self.name_email], [], [])

    def test_ack_in_reply(self):
        self.assertTagsEqual('> Acked-by: %s\n' % self.name_email, [], [], [])


class CoverLetterTagsTest(TestCase):

    fixtures = ['default_tags', 'default_states']

    def assert_tags_counts_equal(self, submission, acked, reviewed, tested):
        sub_obj = Submission.objects.get(pk=submission.pk)

        def count(tag_name):
            try:
                return sub_obj.submissiontag_set.get(tag__name=tag_name).count
            except SubmissionTag.DoesNotExist:
                return 0

        counts = (count('Acked-by'), count('Reviewed-by'), count('Tested-by'))
        self.assertEqual(counts, (acked, reviewed, tested))

    def _parse_mbox(self, how_many, listid):
        mbox = mailbox.mbox(os.path.join(TEST_MAIL_DIR,
                                         '0019-cover-tags.mbox'),
                            create=False)
        for i, msg in enumerate(mbox, start=1):
            if i > how_many:
                break
            parse_mail(msg, listid)
        mbox.close()

    def test_tagged_cover(self):
        project = create_project()
        self._parse_mbox(3, project.listid)
        series = Series.objects.get(project=project)
        self.assert_tags_counts_equal(series.cover_letter, 1, 0, 0)
        self.assert_tags_counts_equal(SeriesPatch.objects.get(series=series,
                                                              number=1).patch,
                                      1, 0, 0)

    def test_cover_and_patch_tagging(self):
        project = create_project()
        self._parse_mbox(4, project.listid)
        series = Series.objects.get(project=project)
        self.assert_tags_counts_equal(series.cover_letter, 1, 0, 0)
        self.assert_tags_counts_equal(SeriesPatch.objects.get(series=series,
                                                              number=1).patch,
                                      2, 0, 0)


class PatchTagsTest(TransactionTestCase):

    fixtures = ['default_tags']
    ACK = 1
    REVIEW = 2
    TEST = 3

    def setUp(self):
        self.patch = create_patch()
        self.patch.project.use_tags = True
        self.patch.project.save()

    def assertTagsCountsEqual(self, patch, acks, reviews, tests):  # noqa
        patch = Patch.objects.get(pk=patch.pk)

        def count(name):
            try:
                return patch.submissiontag_set.get(tag__name=name).count
            except SubmissionTag.DoesNotExist:
                return 0

        counts = (
            count(name='Acked-by'),
            count(name='Reviewed-by'),
            count(name='Tested-by'),
        )

        self.assertEqual(counts, (acks, reviews, tests))

    def create_tag(self, tagtype=None):
        tags = {
            self.ACK: 'Acked',
            self.REVIEW: 'Reviewed',
            self.TEST: 'Tested'
        }
        if tagtype not in tags:
            return ''

        return '%s-by: Test Tagger <tagger@example.com>\n' % tags[tagtype]

    def create_tag_comment(self, patch, tagtype=None):
        comment = create_comment(
            submission=patch,
            content=self.create_tag(tagtype))
        return comment

    def test_no_comments(self):
        self.assertTagsCountsEqual(self.patch, 0, 0, 0)

    def test_no_tag_comment(self):
        self.create_tag_comment(self.patch, None)
        self.assertTagsCountsEqual(self.patch, 0, 0, 0)

    def test_single_comment(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsCountsEqual(self.patch, 1, 0, 0)

    def test_multiple_comments_with_same_tag_value(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsCountsEqual(self.patch, 1, 0, 0)

    def test_multiple_comment_types(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.create_tag_comment(self.patch, self.REVIEW)
        self.create_tag_comment(self.patch, self.TEST)
        self.assertTagsCountsEqual(self.patch, 1, 1, 1)

    def test_comment_add(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsCountsEqual(self.patch, 1, 0, 0)
        self.create_tag_comment(self.patch, self.REVIEW)
        self.assertTagsCountsEqual(self.patch, 1, 1, 0)

    def test_comment_update(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsCountsEqual(self.patch, 1, 0, 0)

        comment.content += self.create_tag(self.REVIEW)
        comment.save()
        self.assertTagsCountsEqual(self.patch, 1, 1, 0)

    def test_comment_delete(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsCountsEqual(self.patch, 1, 0, 0)
        comment.delete()
        self.assertTagsCountsEqual(self.patch, 0, 0, 0)

    def test_single_comment_multiple_tags(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        comment.content += self.create_tag(self.REVIEW)
        comment.save()
        self.assertTagsCountsEqual(self.patch, 1, 1, 0)

    def test_multiple_comments_multiple_tags(self):
        c1 = self.create_tag_comment(self.patch, self.ACK)
        c1.content += self.create_tag(self.REVIEW)
        c1.save()
        self.assertTagsCountsEqual(self.patch, 1, 1, 0)


class PatchTagManagerTest(PatchTagsTest):

    def assertTagsEqual(self, patch, acks, reviews, tests):  # noqa
        tagattrs = {}
        for tag in Tag.objects.all():
            tagattrs[tag.name] = tag.attr_name

        # force project.tags to be queried outside of the assertNumQueries
        patch.project.tags

        # we should be able to do this with two queries: one for
        # the patch table lookup, and the prefetch_related for the
        # projects table.
        with self.assertNumQueries(2):
            patch = Patch.objects.with_tag_counts(project=patch.project) \
                .get(pk=patch.pk)

            counts = (
                getattr(patch, tagattrs['Acked-by']),
                getattr(patch, tagattrs['Reviewed-by']),
                getattr(patch, tagattrs['Tested-by']),
            )

        self.assertEqual(counts, (acks, reviews, tests))
