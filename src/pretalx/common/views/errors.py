import urllib
from contextlib import suppress

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponseServerError
from django.template import TemplateDoesNotExist, loader
from django.urls import get_callable

from pretalx.common.text.phrases import phrases


def handle_500(request):
    try:
        template = loader.get_template("500.html")
    except TemplateDoesNotExist:  # pragma: no cover
        return HttpResponseServerError(
            "Internal server error. Please contact the administrator for details.",
            content_type="text/html",
        )
    context = {}
    with suppress(
        Exception
    ):  # This should never fail, but can't be too cautious in error views
        context["request_path"] = urllib.parse.quote(request.path)
    return HttpResponseServerError(template.render(context))


def handle_418(request):
    try:
        template = loader.get_template("418.html")
    except TemplateDoesNotExist:  # pragma: no cover
        return HttpResponseServerError(
            "Internal server error. Please contact the administrator for details.",
            content_type="text/html",
        )
    context = {"phrases": phrases}
    with suppress(
        Exception
    ):  # This should never fail, but can't be too cautious in error views
        context["request_path"] = urllib.parse.quote(request.path)
    class HttpResponseTeapot(HttpResponseServerError):
        status_code = 418
    return HttpResponseTeapot(template.render(context))


def handle_425(request):
    try:
        template = loader.get_template("425.html")
    except TemplateDoesNotExist:  # pragma: no cover
        return HttpResponseServerError(
            "Internal server error. Please contact the administrator for details.",
            content_type="text/html",
        )
    context = {"phrases": phrases}
    with suppress(
        Exception
    ):  # This should never fail, but can't be too cautious in error views
        context["request_path"] = urllib.parse.quote(request.path)
    class HttpResponseTooEarly(HttpResponseServerError):
        status_code = 425
    return HttpResponseTooEarly(template.render(context))


def error_view(status_code):
    if status_code == 4031:
        return get_callable(settings.CSRF_FAILURE_VIEW)
    if status_code == 418:
        return handle_418
    if status_code == 425:
        return handle_425
    if status_code == 500:
        return handle_500
    exceptions = {
        400: SuspiciousOperation,
        403: PermissionDenied,
        404: Http404,
    }
    exception = exceptions[status_code]

    def error_view_function(request, *args, **kwargs):
        raise exception

    return error_view_function
