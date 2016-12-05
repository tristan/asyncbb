import asyncio
import asyncpg
import configparser
import os
import tornado.ioloop
import tornado.options
import tornado.web
import sys
import urllib
from . import database

from tornado.log import access_log
from .log import log

async def prepare_database(db_config):

    connection_pool = await asyncpg.create_pool(**db_config)
    async with connection_pool.acquire() as con:
        await database.create_tables(con)

    return connection_pool

class Application(tornado.web.Application):

    def __init__(self, urls, config=None, **kwargs):

        if config:
            self.config = config
        else:
            self.config = self.process_config()

        super(Application, self).__init__(urls, debug=self.config['general'].getboolean('debug'), **kwargs)

        self.asyncio_loop = asyncio.get_event_loop()
        if 'database' in self.config:
            self.connection_pool = self.asyncio_loop.run_until_complete(
                prepare_database(self.config['database']))
        else:
            self.connection_pool = None

    def process_config(self):

        tornado.options.define("config", default="config-localhost.ini", help="configuration file")
        tornado.options.define("port", default=8888, help="port to listen on")
        tornado.options.parse_command_line()

        config = configparser.ConfigParser()
        if os.path.exists(tornado.options.options.config):
            config.read(tornado.options.options.config)

        # verify config and set default values
        if 'general' not in config:
            config['general'] = {'debug': 'false'}
        elif 'debug' not in config['general']:
            config['debug'] = 'false'

        if 'DATABASE_URL' in os.environ:
            if 'PGSQL_STUNNEL_ENABLED' in os.environ and os.environ['PGSQL_STUNNEL_ENABLED'] == '1':
                p = urllib.parse.urlparse(os.environ['DATABASE_URL'])
                config['database'] = {
                    'host': '/tmp/.s.PGSQL.6101',
                    'database': p.path[1:]
                }
                if p.username:
                    config['database']['user'] = p.username
                if p.password:
                    config['database']['password'] = p.password
            else:
                config['database'] = {'dsn': os.environ['DATABASE_URL']}
        elif 'database' not in config:
            raise Exception("Missing database configuration")

        return config

    def start(self):
        # verify python version
        if sys.version_info[:2] != (3, 5):
            print("Requires python version 3.5")
            sys.exit(1)

        # install asyncio io loop (NOTE: must be done before app creation
        # as the autoreloader will also install one
        tornado.platform.asyncio.AsyncIOMainLoop().install()

        self.listen(tornado.options.options.port, xheaders=True)
        log.info("Starting HTTP Server on port: {}".format(tornado.options.options.port))
        self.asyncio_loop.run_forever()


class _RequestDispatcher(tornado.web._RequestDispatcher):
    def set_request(self, request):
        super(_RequestDispatcher, self).set_request(request)

class DebuggingApplication(Application):

    def listen(self, *args, **kwargs):
        self._server = super(DebuggingApplication, self).listen(*args, **kwargs)

    def start_request(self, server_conn, request_conn):
        return _RequestDispatcher(self, request_conn)

    def log_request(self, handler):
        super(DebuggingApplication, self).log_request(handler)
        size = self.connection_pool._queue.qsize()
        access_log.info("Stats for Server on port '{}': Active Server connections: {}, DB Connections in pool: {}, DB Pool size: {}".format(
            tornado.options.options.port,
            len(self._server._connections),
            size,
            self.connection_pool._con_count
        ))
