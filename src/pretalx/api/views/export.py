# SPDX-FileCopyrightText: 2025-present Florian Moesch
# SPDX-License-Identifier: AGPL-3.0-only WITH LicenseRef-Pretalx-AGPL-3.0-Terms

from rest_framework import permissions
from rest_framework.views import APIView

from pretalx.agenda.views.utils import get_schedule_exporter_content
from pretalx.event.models import Event


class ExporterProxyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event, exporter):
        request.event = Event.objects.get(slug=event)
        schedule = request.event.current_schedule
        return get_schedule_exporter_content(request, exporter, schedule)
