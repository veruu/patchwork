# Patchwork - automated patch tracking system
# Copyright (C) 2018 Red Hat
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
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.reverse import reverse
from rest_framework.serializers import HyperlinkedModelSerializer
from rest_framework.serializers import SerializerMethodField

from patchwork.api.base import PatchworkPermission
from patchwork.api.filters import CommentFilter
from patchwork.api.embedded import PersonSerializer
from patchwork.api.embedded import ProjectSerializer
from patchwork.models import Comment


class CommentListSerializer(HyperlinkedModelSerializer):

    submitter = PersonSerializer(read_only=True)
    tags = SerializerMethodField()
    subject = SerializerMethodField()
    parent = SerializerMethodField(source='submission')

    def get_parent(self, instance):
        attrs = {'subject': instance.submission.name,
                 'msgid': instance.submission.msgid,
                 'date': instance.submission.date}

        if hasattr(instance.submission, 'patch'):
            attrs['url'] = self.context.get('request').build_absolute_uri(
                reverse('api-patch-detail', args=[instance.submission.id]))
        else:
            attrs['url'] = self.context.get('request').build_absolute_uri(
                reverse('api-cover-detail', args=[instance.submission.id]))

        return attrs

    def get_subject(self, instance):
        return email.parser.Parser().parsestr(instance.headers,
                                              True).get('Subject', '')

    def get_tags(self, instance):
        # TODO implement after we get support for tags on comments
        return {}

    class Meta:
        model = Comment
        fields = ('id', 'url', 'msgid', 'date', 'subject', 'submitter',
                  'parent', 'tags')
        read_only_fields = fields
        extra_kwargs = {
            'url': {'view_name': 'api-comment-detail'},
        }


class CommentDetailSerializer(CommentListSerializer):

    headers = SerializerMethodField()
    project = ProjectSerializer(source='submission.project', read_only=True)

    def get_headers(self, comment):
        if comment.headers:
            return email.parser.Parser().parsestr(comment.headers, True)

    class Meta:
        model = Comment
        fields = CommentListSerializer.Meta.fields + (
            'content', 'headers', 'project'
        )
        read_only_fields = fields
        extra_kwargs = CommentListSerializer.Meta.extra_kwargs


class CommentList(ListAPIView):
    """List comments"""

    permission_classes = (PatchworkPermission,)
    serializer_class = CommentListSerializer
    filter_class = CommentFilter
    search_fields = ('subject',)
    ordering_fields = ('id', 'subject', 'date', 'submitter')
    ordering = 'id'

    def get_queryset(self):
        return Comment.objects.all().select_related(
            'submission'
        ).prefetch_related('related_tags').defer('content')


class CommentDetail(RetrieveUpdateAPIView):
    """Show a comment"""

    permission_classes = (PatchworkPermission,)
    serializer_class = CommentDetailSerializer

    def get_queryset(self):
        return Comment.objects.all().select_related(
            'submission'
        ).prefetch_related('related_tags')
