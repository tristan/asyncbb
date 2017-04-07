import tornado.escape
import tornado.web
import traceback

from .errors import JSONHTTPError
from .log import log

DEFAULT_JSON_ARGUMENT = object()

class JsonBodyMixin:

    @property
    def json(self):
        if not hasattr(self, '_json'):
            data = self.request.body.decode('utf-8').strip()
            self._json = tornado.escape.json_decode(data) if data else {}
        return self._json

    def get_json_argument(self, name, default=DEFAULT_JSON_ARGUMENT):
        if name not in self.json:
            if default is DEFAULT_JSON_ARGUMENT:
                raise JSONHTTPError(400, "missing_arguments")
            return default
        return self.json[name]

class BaseHandler(JsonBodyMixin, tornado.web.RequestHandler):

    def prepare(self):

        # log the full request and headers if the log level is set to debug
        if log.level == 10:
            log.debug("Preparing request: {} {}".format(self.request.method, self.request.path))
            for k, v in self.request.headers.items():
                log.debug("{}: {}".format(k, v))

        return super().prepare()

    def write_error(self, status_code, **kwargs):
        """Overrides tornado's default error writing handler to return json data instead of a html template"""
        rval = {'type': 'error', 'payload': {}}
        if 'exc_info' in kwargs:
            # check exc type and if JSONHTTPError check for extra details
            exc_type, exc_value, exc_traceback = kwargs['exc_info']
            if isinstance(exc_value, JSONHTTPError):
                if exc_value.body is not None:
                    rval = exc_value.body
                elif exc_value.code is not None:
                    rval['payload']['code'] = exc_value.code
            # if we're in debug mode, add the exception data to the response
            if self.application.config['general'].getboolean('debug'):
                rval['exc_info'] = traceback.format_exception(*kwargs["exc_info"])
        log.error(rval)
        self.write(rval)

    def run_in_executor(self, func, *args):
        return self.application.asyncio_loop.run_in_executor(self.application.executor, func, *args)
