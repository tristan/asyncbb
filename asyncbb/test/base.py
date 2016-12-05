import asyncio
import configparser
import logging
import tornado.escape
import tornado.web
import warnings

from tornado.platform.asyncio import AsyncIOLoop
from tornado.testing import AsyncHTTPTestCase

from asyncbb.web import Application

logging.basicConfig()

class AsyncHandlerTest(AsyncHTTPTestCase):

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
        self._config = configparser.ConfigParser()
        conf = {
            'general': {'debug': True},
        }
        if extraconf:
            conf.update(extraconf)
        self._config.read_dict(conf)
        super(AsyncHandlerTest, self).setUp()

    def get_app(self):
        return Application(self.get_urls(), config=self._config, autoreload=False)

    def get_urls(self):
        raise NotImplementedError

    def tearDown(self):
        super(AsyncHandlerTest, self).tearDown()

    def fetch(self, req, **kwargs):
        if 'body' in kwargs and isinstance(kwargs['body'], dict):
            kwargs.setdefault('headers', {})['Content-Type'] = "application/json"
            kwargs['body'] = tornado.escape.json_encode(kwargs['body'])
        # default raise_error to false
        if 'raise_error' not in kwargs:
            kwargs['raise_error'] = False
        return self.http_client.fetch(self.get_url(req), self.stop, **kwargs)
