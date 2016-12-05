import tornado.escape
import tornado.web
import traceback

from .database import HandlerDatabasePoolContext
from .errors import JSONHTTPError

DEFAULT_JSON_ARGUMENT = object()

class BaseHandler(tornado.web.RequestHandler):

    @property
    def db(self):
        if not hasattr(self, '_dbcontext'):
            self._dbcontext = HandlerDatabasePoolContext(self, self.application.connection_pool)
        return self._dbcontext

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
        self.write(rval)
