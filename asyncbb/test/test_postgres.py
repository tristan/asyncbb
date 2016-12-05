from .base import AsyncHandlerTest
from .database import requires_database

from asyncbb.handlers import BaseHandler
from asyncbb.database import DatabaseMixin
from tornado.testing import gen_test

class Handler(DatabaseMixin, BaseHandler):

    async def get(self):

        key = self.get_query_argument('key')
        value = self.get_query_argument('value')

        async with self.db:
            await self.db.execute("INSERT INTO store VALUES ($1, $2)", key, value)
            await self.db.commit()

        self.set_status(204)
        self.finish()

class DatabaseTest(AsyncHandlerTest):

    def get_urls(self):
        return [(r'^/$', Handler)]

    @gen_test
    @requires_database
    async def test_database_connection(self):

        async with self.pool.acquire() as con:
            await con.execute("CREATE TABLE store (key VARCHAR PRIMARY KEY, value VARCHAR)")

        await self.fetch('/?key=TESTKEY&value=1')

        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT * FROM store WHERE key = $1", "TESTKEY")
            self.assertEqual(row['value'], '1')
