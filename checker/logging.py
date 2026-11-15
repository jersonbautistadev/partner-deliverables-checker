import logging


class SafeRequestFilter(logging.Filter):
    def filter(self, record):
        request = getattr(record, 'request', None)
        route = getattr(getattr(request, 'resolver_match', None), 'url_name', 'unresolved')
        record.msg = 'http_error route=%s status=%s'
        record.args = (route, getattr(record, 'status_code', 500))
        record.exc_info = None
        record.exc_text = None
        record.request = None
        return True
