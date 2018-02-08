# Patchwork - automated patch tracking system
# Copyright (C) 2016 Linaro Corporation
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

from django.db.models import Q

import email.parser

from django.utils.translation import ugettext_lazy as _
from rest_framework.generics import ListAPIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.relations import RelatedField
from rest_framework.reverse import reverse
from rest_framework.serializers import HyperlinkedModelSerializer
from rest_framework.serializers import SerializerMethodField

from patchwork.api.base import PatchworkPermission
from patchwork.api.filters import PatchFilter
from patchwork.api.embedded import PersonSerializer
from patchwork.api.embedded import ProjectSerializer
from patchwork.api.embedded import SeriesSerializer
from patchwork.api.embedded import UserSerializer
from patchwork.models import Patch
from patchwork.models import RelatedTag
from patchwork.models import SeriesPatch
from patchwork.models import State
from patchwork.parser import clean_subject


class StateField(RelatedField):
    """Avoid the need for a state endpoint.

    NOTE(stephenfin): This field will only function for State names consisting
    of alphanumeric characters, underscores and single spaces. In Patchwork
    2.0+, we should consider adding a slug field to the State object and make
    use of the SlugRelatedField in DRF.
    """
    default_error_messages = {
        'required': _('This field is required.'),
        'invalid_choice': _('Invalid state {name}. Expected one of: '
                            '{choices}.'),
        'incorrect_type': _('Incorrect type. Expected string value, received '
                            '{data_type}.'),
    }

    @staticmethod
    def format_state_name(state):
        return ' '.join(state.split('-'))

    def to_internal_value(self, data):
        try:
            data = self.format_state_name(data)
            return self.get_queryset().get(name__iexact=data)
        except State.DoesNotExist:
            self.fail('invalid_choice', name=data, choices=', '.join([
                self.format_state_name(x.name) for x in self.get_queryset()]))
        except (TypeError, ValueError):
            self.fail('incorrect_type', data_type=type(data).__name__)

    def to_representation(self, obj):
        return obj.slug

    def get_queryset(self):
        return State.objects.all()


class PatchListSerializer(HyperlinkedModelSerializer):

    project = ProjectSerializer(read_only=True)
    state = StateField()
    submitter = PersonSerializer(read_only=True)
    delegate = UserSerializer()
    mbox = SerializerMethodField()
    series = SeriesSerializer(many=True, read_only=True)
    check = SerializerMethodField()
    checks = SerializerMethodField()
    tags = SerializerMethodField()

    def get_mbox(self, instance):
        request = self.context.get('request')
        return request.build_absolute_uri(instance.get_mbox_url())

    def get_tags(self, instance):
        tags = instance.patch_project.tags
        if not tags:
            return {}

        all_tags = {tag.name: [] for tag in tags}

        patch_tags = RelatedTag.objects.filter(
            Q(submission__id=instance.id)
            | Q(comment__id__in=[comment.id for comment in
                                 instance.comments.all()])
        )
        cover = SeriesPatch.objects.get(
            patch_id=instance.id).series.cover_letter
        if cover:
            cover_tags = RelatedTag.objects.filter(
                Q(submission__id=cover.submission_ptr_id)
                | Q(comment__id__in=[comment.id for comment in
                                     cover.comments.all()])
            )
        else:
            cover_tags = RelatedTag.objects.none()

        for related_tag in (patch_tags | cover_tags):
            all_tags[related_tag.tag.name].extend([value.value for value in
                                                   related_tag.values.all()])

        # Sanitize the values -- remove possible duplicates and unused tags
        for tag in tags:
            if all_tags[tag.name]:
                all_tags[tag.name] = set(all_tags[tag.name])
            else:
                del(all_tags[tag.name])

        return all_tags

    def get_check(self, instance):
        return instance.combined_check_state

    def get_checks(self, instance):
        return self.context.get('request').build_absolute_uri(
            reverse('api-check-list', kwargs={'patch_id': instance.id}))

    class Meta:
        model = Patch
        fields = ('id', 'url', 'project', 'msgid', 'date', 'name',
                  'commit_ref', 'pull_url', 'state', 'archived', 'hash',
                  'submitter', 'delegate', 'mbox', 'series', 'check', 'checks',
                  'tags')
        read_only_fields = ('project', 'msgid', 'date', 'name', 'hash',
                            'submitter', 'mbox', 'mbox', 'series', 'check',
                            'checks', 'tags')
        extra_kwargs = {
            'url': {'view_name': 'api-patch-detail'},
        }


class PatchDetailSerializer(PatchListSerializer):

    headers = SerializerMethodField()
    prefixes = SerializerMethodField()

    def get_headers(self, patch):
        if patch.headers:
            return email.parser.Parser().parsestr(patch.headers, True)

    def get_prefixes(self, instance):
        return clean_subject(instance.name)[1]

    class Meta:
        model = Patch
        fields = PatchListSerializer.Meta.fields + (
            'headers', 'content', 'diff', 'prefixes')
        read_only_fields = PatchListSerializer.Meta.read_only_fields + (
            'headers', 'content', 'diff', 'prefixes')
        extra_kwargs = PatchListSerializer.Meta.extra_kwargs


class PatchList(ListAPIView):
    """List patches."""

    permission_classes = (PatchworkPermission,)
    serializer_class = PatchListSerializer
    filter_class = PatchFilter
    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'project', 'date', 'state', 'archived',
                       'submitter', 'check')
    ordering = 'id'

    def get_queryset(self):
        return Patch.objects.all()\
            .prefetch_related('series', 'check_set')\
            .select_related('project', 'state', 'submitter', 'delegate')\
            .defer('content', 'diff', 'headers')


class PatchDetail(RetrieveUpdateAPIView):
    """Show a patch."""

    permission_classes = (PatchworkPermission,)
    serializer_class = PatchDetailSerializer

    def get_queryset(self):
        return Patch.objects.all()\
            .prefetch_related('series', 'check_set')\
            .select_related('project', 'state', 'submitter', 'delegate')
