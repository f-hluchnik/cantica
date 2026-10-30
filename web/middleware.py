from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class LiveMiddleware:
    """Answer /live before host validation.

    Fly's health checks may use the machine's private IP as the Host header, which is not in
    ALLOWED_HOSTS; CommonMiddleware would reject that with 400. This must be first in MIDDLEWARE.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path == '/live':
            return HttpResponse('ok', content_type='text/plain')
        return self.get_response(request)
