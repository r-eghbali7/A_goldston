from django.http import HttpResponsePermanentRedirect


class WWWRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        host = request.get_host().split(':')[0]

        if host == 'www.goldestone.ir':
            new_url = f'https://goldestone.ir{request.get_full_path()}'
            return HttpResponsePermanentRedirect(new_url)

        return self.get_response(request)