# Patchwork - automated patch tracking system
# Copyright (C) 2016 Stephen Finucane <stephen@that.guru>
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

import email.parser

from rest_framework.generics import ListAPIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.serializers import HyperlinkedModelSerializer
from rest_framework.serializers import SerializerMethodField

from patchwork.api.filters import CoverLetterFilter
from patchwork.api.embedded import PersonSerializer
from patchwork.api.embedded import ProjectSerializer
from patchwork.api.embedded import SeriesSerializer
from patchwork.models import CoverLetter
from patchwork.models import SubmissionTag


class CoverLetterListSerializer(HyperlinkedModelSerializer):

    project = ProjectSerializer(read_only=True)
    submitter = PersonSerializer(read_only=True)
    mbox = SerializerMethodField()
    series = SeriesSerializer(many=True, read_only=True)
    tags = SerializerMethodField()

    def get_mbox(self, instance):
        request = self.context.get('request')
        return request.build_absolute_uri(instance.get_mbox_url())

    def get_tags(self, instance):
        return {submissiontag.tag.name: [value.value for value in
                                         submissiontag.values.all()]
                for submissiontag in
                SubmissionTag.objects.filter(submission_id=instance.id)}

    class Meta:
        model = CoverLetter
        fields = ('id', 'url', 'project', 'msgid', 'date', 'name', 'submitter',
                  'mbox', 'series', 'tags')
        read_only_fields = fields
        extra_kwargs = {
            'url': {'view_name': 'api-cover-detail'},
        }


class CoverLetterDetailSerializer(CoverLetterListSerializer):

    headers = SerializerMethodField()

    def get_headers(self, instance):
        if instance.headers:
            return email.parser.Parser().parsestr(instance.headers, True)

    class Meta:
        model = CoverLetter
        fields = CoverLetterListSerializer.Meta.fields + ('headers', 'content')
        read_only_fields = fields
        extra_kwargs = CoverLetterListSerializer.Meta.extra_kwargs


class CoverLetterList(ListAPIView):
    """List cover letters."""

    serializer_class = CoverLetterListSerializer
    filter_class = CoverLetterFilter
    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'date', 'submitter')
    ordering = 'id'

    def get_queryset(self):
        return CoverLetter.objects.all().prefetch_related('series')\
            .select_related('project', 'submitter')\
            .defer('content', 'headers')


class CoverLetterDetail(RetrieveAPIView):
    """Show a cover letter."""

    serializer_class = CoverLetterDetailSerializer

    def get_queryset(self):
        return CoverLetter.objects.all().prefetch_related('series')\
            .select_related('project', 'submitter')
