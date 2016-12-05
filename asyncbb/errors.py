import tornado.web


class JSONHTTPError(tornado.web.HTTPError):
    def __init__(self, status_code=500, log_message=None, code=None, body=None, *args, **kwargs):
        super(JSONHTTPError, self).__init__(status_code=status_code, log_message=log_message, *args, **kwargs)
        self.code = code
        self.body = body


class DatabaseError(Exception):
    def __init__(self, response):
        self.message = response
