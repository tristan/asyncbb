import tornado.web

class JSONHTTPError(tornado.web.HTTPError):
    def __init__(self, status_code=500, log_message=None, code=None, body=None, *args, **kwargs):
        super(JSONHTTPError, self).__init__(status_code=status_code, log_message=log_message, *args, **kwargs)
        self.code = code
        self.body = body


class DatabaseError(Exception):
    def __init__(self, response):
        self.message = response

class JsonRPCError(Exception):
    def __init__(self, request_id, code, message, data, is_notification=False):
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message
        self.data = data
        self.is_notification = is_notification

    def format(self, request=None):
        if request:
            if 'id' not in request:
                self.is_notification = True
            else:
                self.request_id = request['id']
        # if the request was a notification, return nothing
        if self.is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": self.code,
                "message": self.message,
                "data": self.data,
            },
            "id": self.request_id
        }

    def __repr__(self):
        return "Json RPC Error ({}): {}".format(self.code, self.message)

class JsonRPCInvalidParamsError(JsonRPCError):
    def __init__(self, *, request=None, data=None):
        super().__init__(request.get('id') if request else None,
                         -32602, "Invalid params", data,
                         'id' not in request if request else False)

class JsonRPCInternalError(JsonRPCError):
    def __init__(self, *, request=None, data=None):
        super().__init__(request.get('id') if request else None,
                         -32603, "Internal Error", data,
                         'id' not in request if request else False)
