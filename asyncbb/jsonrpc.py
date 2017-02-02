import asyncio
import json
from tornado.escape import json_decode

from .errors import JsonRPCError, JsonRPCInvalidParamsError, JsonRPCInternalError

def _parse_error(request, data=None):
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32700,
            "message": "Parse error",
            "data": data
        },
        "id": None
    }

def _invalid_request(request, data=None):
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32600,
            "message": "Invalid request",
            "data": data
        },
        "id": None
    }

def _method_not_found(request, data=None):
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": "Method not found",
            "data": data
        },
        "id": request['id']
    }

def map_jsonrpc_arguments(map):
    def wrap(fn):
        if not isinstance(map, dict):
            raise TypeError("map must be a dict")
        fn.keyword_map = map
        return fn
    return wrap

class JsonRPCBase:

    """Base class for building jsonrpc apis"""

    async def __call__(self, request):

        if isinstance(request, (bytes, str)):
            try:
                request = json_decode(request)
            except json.JSONDecodeError:
                return _parse_error(request)

        # check batch request
        if isinstance(request, list):
            resp = []
            for r in request:
                result = await self._handle_single_request(r)
                if result:
                    resp.append(result)
            # if all were notifications
            if not resp:
                return None
            return resp
        # standard single request
        return await self._handle_single_request(request)

    async def _handle_single_request(self, request):
        # check for invalid request
        if 'method' not in request or 'jsonrpc' not in request or request['jsonrpc'] != "2.0":
            return _invalid_request(request)

        method = request['method']
        if method.startswith('.') or method.startswith('_') or not hasattr(self, method) or not callable(getattr(self, method)):
            return _method_not_found(request)
        fn = getattr(self, method)

        params = request.get('params')

        if isinstance(params, list):
            args = params
            kwargs = {}
        elif isinstance(params, dict):
            args = []
            if hasattr(fn, 'keyword_map'):
                kwargs = {}
                for key, value in params.items():
                    if key in fn.keyword_map:
                        kwargs[fn.keyword_map[key]] = value
                    else:
                        kwargs[key] = value
            else:
                kwargs = params

        else:
            args = []
            kwargs = {}

        try:
            result = fn(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
        except TypeError:
            return JsonRPCInvalidParamsError(request=request, data={'id': 'bad_arguments', 'message': "Bad Arguments"}).format()
        except JsonRPCError as e:
            return e.format(request)
        except:
            return JsonRPCInternalError(request=request).format()

        # handle notification requests
        if 'id' not in request:
            return None

        # send normal response
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request['id']
        }
