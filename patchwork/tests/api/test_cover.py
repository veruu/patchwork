# Patchwork - automated patch tracking system
# Copyright (C) 2016 Linaro Corporation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import email.parser
import unittest

from django.conf import settings
from django.urls import reverse

from patchwork.tests.utils import create_cover
from patchwork.tests.utils import create_maintainer
from patchwork.tests.utils import create_person
from patchwork.tests.utils import create_project
from patchwork.tests.utils import create_series
from patchwork.tests.utils import create_user

if settings.ENABLE_REST_API:
    from rest_framework import status
    from rest_framework.test import APITestCase
else:
    # stub out APITestCase
    from django.test import TestCase
    APITestCase = TestCase  # noqa


@unittest.skipUnless(settings.ENABLE_REST_API, 'requires ENABLE_REST_API')
class TestCoverLetterAPI(APITestCase):
    fixtures = ['default_tags']

    @staticmethod
    def api_url(item=None, version=None):
        kwargs = {}
        if version:
            kwargs['version'] = version

        if item is None:
            return reverse('api-cover-list', kwargs=kwargs)
        kwargs['pk'] = item
        return reverse('api-cover-detail', kwargs=kwargs)

    def assertSerialized(self, cover_obj, cover_json):
        self.assertEqual(cover_obj.id, cover_json['id'])
        self.assertEqual(cover_obj.name, cover_json['name'])
        self.assertIn(cover_obj.get_mbox_url(), cover_json['mbox'])
        self.assertIn(cover_obj.get_absolute_url(), cover_json['web_url'])
        self.assertIn('comments', cover_json)

        # nested fields

        self.assertEqual(cover_obj.submitter.id,
                         cover_json['submitter']['id'])

    def test_list(self):
        """Validate we can list cover letters."""
        resp = self.client.get(self.api_url())
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(0, len(resp.data))

        person_obj = create_person(email='test@example.com')
        project_obj = create_project(linkname='myproject')
        series = create_series()
        cover_obj = create_cover(project=project_obj, submitter=person_obj,
                                 series=series)

        # anonymous user
        resp = self.client.get(self.api_url())
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(1, len(resp.data))
        self.assertSerialized(cover_obj, resp.data[0])

        # authenticated user
        user = create_user()
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.api_url())
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(1, len(resp.data))
        self.assertSerialized(cover_obj, resp.data[0])

        # test filtering by project
        resp = self.client.get(self.api_url(), {'project': 'myproject'})
        self.assertEqual([cover_obj.id], [x['id'] for x in resp.data])
        resp = self.client.get(self.api_url(), {'project': 'invalidproject'})
        self.assertEqual(0, len(resp.data))

        # test filtering by submitter, both ID and email
        resp = self.client.get(self.api_url(), {'submitter': person_obj.id})
        self.assertEqual([cover_obj.id], [x['id'] for x in resp.data])
        resp = self.client.get(self.api_url(), {
            'submitter': 'test@example.com'})
        self.assertEqual([cover_obj.id], [x['id'] for x in resp.data])
        resp = self.client.get(self.api_url(), {
            'submitter': 'test@example.org'})
        self.assertEqual(0, len(resp.data))

    def test_list_version_1_0(self):
        series = create_series()
        create_cover(series=series)

        resp = self.client.get(self.api_url(version='1.0'))
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(1, len(resp.data))
        self.assertIn('url', resp.data[0])
        self.assertNotIn('mbox', resp.data[0])
        self.assertNotIn('web_url', resp.data[0])

    def test_detail(self):
        """Validate we can get a specific cover letter."""
        series = create_series()
        cover_obj = create_cover(
            headers='Received: from somewhere\nReceived: from another place',
            series=series
        )

        resp = self.client.get(self.api_url(cover_obj.id))
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertSerialized(cover_obj, resp.data)

        # Make sure we don't regress and all headers with the same key are
        # included in the response
        parsed_headers = email.parser.Parser().parsestr(cover_obj.headers,
                                                        True)
        for key, value in parsed_headers.items():
            self.assertIn(value, resp.data['headers'][key])

    def test_detail_version_1_0(self):
        series = create_series()
        cover = create_cover(series=series)

        resp = self.client.get(self.api_url(cover.id, version='1.0'))
        self.assertIn('url', resp.data)
        self.assertNotIn('web_url', resp.data)
        self.assertNotIn('comments', resp.data)

    def test_create_update_delete(self):
        user = create_maintainer()
        user.is_superuser = True
        user.save()
        self.client.force_authenticate(user=user)

        resp = self.client.post(self.api_url(), {'name': 'test cover'})
        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, resp.status_code)

        resp = self.client.patch(self.api_url(), {'name': 'test cover'})
        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, resp.status_code)

        resp = self.client.delete(self.api_url())
        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, resp.status_code)
