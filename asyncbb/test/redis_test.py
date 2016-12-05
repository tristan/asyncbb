from .base import AsyncHandlerTest
from .redis import requires_redis

from asyncbb.handlers import BaseHandler
from asyncbb.redis import RedisMixin
from tornado.testing import gen_test

class Handler(RedisMixin, BaseHandler):

    def get(self):

        key = self.get_query_argument('key')
        value = self.get_query_argument('value')

        self.redis.set(key, value)
        self.set_status(204)

class RedisTest(AsyncHandlerTest):

    def get_urls(self):
        return [(r'^/$', Handler)]

    @gen_test
    @requires_redis
    async def test_redis_connection(self):

        await self.fetch('/?key=TESTKEY&value=1')
        self.assertEqual(self.redis.get("TESTKEY"), '1')
