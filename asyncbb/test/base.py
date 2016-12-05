import asyncio
import configparser
import logging
import testing.postgresql
import tornado.escape
import tornado.web
import warnings

from tornado.platform.asyncio import AsyncIOLoop
from tornado.testing import AsyncHTTPTestCase, get_async_test_timeout, gen_test

from asyncbb.web import Application
from asyncbb.database import HandlerDatabasePoolContext

logging.basicConfig()

POSTGRESQL_FACTORY = testing.postgresql.PostgresqlFactory(cache_initialized_db=True)

class AsyncHandlerTest(AsyncHTTPTestCase):

    @property
    def db(self):
        return self._app.connection_pool.acquire()

    @property
    def log(self):
        return logging.getLogger(self.__class__.__name__)

    def get_new_ioloop(self):
        io_loop = AsyncIOLoop()
        asyncio.set_event_loop(io_loop.asyncio_loop)
        return io_loop

    def setUp(self, extraconf=None):
        # TODO: re-enable this and figure out if any of the warnings matter
        warnings.simplefilter("ignore")
        self._psql = POSTGRESQL_FACTORY()
        self._config = configparser.ConfigParser()
        conf = {
            'general': {'debug': False},
            'database': self._psql.dsn(),
        }
        if extraconf:
            conf.update(extraconf)
        self._config.read_dict(conf)
        super(AsyncHandlerTest, self).setUp()

    def get_app(self):
        return Application(self.get_urls(), config=self._config)

    def get_urls(self):
        raise NotImplemented

    def tearDown(self):
        super(AsyncHandlerTest, self).tearDown()
        self._psql.stop()

    def fetch(self, req, **kwargs):
        if 'body' in kwargs and isinstance(kwargs['body'], dict):
            kwargs.setdefault('headers', {})['Content-Type'] = "application/json"
            kwargs['body'] = tornado.escape.json_encode(kwargs['body'])
        # default raise_error to false
        if 'raise_error' not in kwargs:
            kwargs['raise_error'] = False
        return self.http_client.fetch(self.get_url(req), self.stop, **kwargs)


def async_test(func=None, timeout=None):
    """Used to ensure all database connections are returned to the pool
    before finishing the test"""

    if timeout is None:
        timeout = get_async_test_timeout()

    def wrap(fn):

        @gen_test(timeout=timeout)
        async def wrapper(self, *args, **kwargs):

            f = fn(self, *args, **kwargs)
            if asyncio.iscoroutine(f):
                await f

            while self._app.connection_pool._con_count != self._app.connection_pool._queue.qsize():
                future = asyncio.Future()
                self.io_loop.add_callback(lambda: future.set_result(True))
                await future

        return wrapper

    if func is not None:
        return wrap(func)
    else:
        return wrap
