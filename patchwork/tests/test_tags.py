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

from django.test import TestCase
from django.test import TransactionTestCase

from patchwork.models import Patch
from patchwork.models import SubmissionTag
from patchwork.models import Tag
from patchwork.tests.utils import create_comment
from patchwork.tests.utils import create_patch


class ExtractTagsTest(TestCase):

    fixtures = ['default_tags']
    email = 'test@example.com'
    name_email = 'test name <' + email + '>'

    def assertTagsEqual(self, str, acks, reviews, tests):  # noqa
        patch = create_patch(content=str)
        extracted = patch._extract_tags(Tag.objects.all())
        self.assertEqual(
            (acks, reviews, tests),
            (len(extracted.get(Tag.objects.get(name='Acked-by'), [])),
             len(extracted.get(Tag.objects.get(name='Reviewed-by'), [])),
             len(extracted.get(Tag.objects.get(name='Tested-by'), [])))
        )

    def test_empty(self):
        self.assertTagsEqual('', 0, 0, 0)

    def test_no_tag(self):
        self.assertTagsEqual('foo', 0, 0, 0)

    def test_ack(self):
        self.assertTagsEqual('Acked-by: %s' % self.name_email, 1, 0, 0)

    def test_ack_email_only(self):
        self.assertTagsEqual('Acked-by: %s' % self.email, 1, 0, 0)

    def test_reviewed(self):
        self.assertTagsEqual('Reviewed-by: %s' % self.name_email, 0, 1, 0)

    def test_tested(self):
        self.assertTagsEqual('Tested-by: %s' % self.name_email, 0, 0, 1)

    def test_ack_after_newline(self):
        self.assertTagsEqual('\nAcked-by: %s' % self.name_email, 1, 0, 0)

    def test_multiple_acks(self):
        str = 'Acked-by: %s\nAcked-by: %s\n' % ((self.name_email,) * 2)
        self.assertTagsEqual(str, 2, 0, 0)

    def test_multiple_types(self):
        str = 'Acked-by: %s\nAcked-by: %s\nReviewed-by: %s\n' % (
            (self.name_email,) * 3)
        self.assertTagsEqual(str, 2, 1, 0)

    def test_lower(self):
        self.assertTagsEqual('acked-by: %s' % self.name_email, 1, 0, 0)

    def test_upper(self):
        self.assertTagsEqual('ACKED-BY: %s' % self.name_email, 1, 0, 0)

    def test_ack_in_reply(self):
        self.assertTagsEqual('> Acked-by: %s\n' % self.name_email, 0, 0, 0)


class SubmissionTagsTest(TransactionTestCase):

    fixtures = ['default_tags']
    ACK = 1
    REVIEW = 2
    TEST = 3

    def setUp(self):
        self.patch = create_patch()
        self.patch.project.use_tags = True
        self.patch.project.save()

    def assertTagsEqual(self, patch, acks, reviews, tests):  # noqa
        patch = Patch.objects.get(pk=patch.pk)

        def count(submission, name):
            return SubmissionTag.objects.filter(submission=patch,
                                                tag__name=name).count()

        counts = (
            count(patch, 'Acked-by'),
            count(patch, 'Reviewed-by'),
            count(patch, 'Tested-by'),
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

        index = SubmissionTag.objects.filter(
            tag__name=tags[tagtype] + '-by'
        ).count()
        return '%s-by: Test Taggeri%d <tagger@example.com>\n' % (
            tags[tagtype], index + 1
        )

    def create_tag_comment(self, patch, tagtype=None):
        comment = create_comment(
            submission=patch,
            content=self.create_tag(tagtype))
        return comment

    def test_no_comments(self):
        self.assertTagsEqual(self.patch, 0, 0, 0)

    def test_no_tag_comment(self):
        self.create_tag_comment(self.patch, None)
        self.assertTagsEqual(self.patch, 0, 0, 0)

    def test_single_comment(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 1, 0, 0)

    def test_multiple_comments(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 2, 0, 0)

    def test_multiple_comment_types(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.create_tag_comment(self.patch, self.REVIEW)
        self.create_tag_comment(self.patch, self.TEST)
        self.assertTagsEqual(self.patch, 1, 1, 1)

    def test_comment_add(self):
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 1, 0, 0)
        self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 2, 0, 0)

    def test_comment_update(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 1, 0, 0)

        comment.content += self.create_tag(self.ACK)
        comment.save()
        self.assertTagsEqual(self.patch, 2, 0, 0)

    def test_comment_delete(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        self.assertTagsEqual(self.patch, 1, 0, 0)
        comment.delete()
        self.assertTagsEqual(self.patch, 0, 0, 0)

    def test_single_comment_multiple_tags(self):
        comment = self.create_tag_comment(self.patch, self.ACK)
        comment.content += self.create_tag(self.REVIEW)
        comment.save()
        self.assertTagsEqual(self.patch, 1, 1, 0)

    def test_multiple_comments_multiple_tags(self):
        c1 = self.create_tag_comment(self.patch, self.ACK)
        c1.content += self.create_tag(self.REVIEW)
        c1.save()
        self.assertTagsEqual(self.patch, 1, 1, 0)
