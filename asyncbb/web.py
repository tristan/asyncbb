import asyncio
import concurrent.futures
import configparser
import logging
import os
import tornado.ioloop
import tornado.options
import tornado.web
import sys
import urllib

from configparser import SectionProxy
from .log import log, SlackLogHandler, configure_logger
from tornado.log import app_log, access_log, gen_log

# verify python version
if sys.version_info[:2] < (3, 5):
    print("Requires python version 3.5 or greater")
    sys.exit(1)

# install asyncio io loop (NOTE: must be done before app creation
# as the autoreloader will also install one
tornado.platform.asyncio.AsyncIOMainLoop().install()

# extra tornado config options
tornado.options.define("config", default="config-localhost.ini", help="configuration file")
tornado.options.define("port", default=8888, help="port to listen on")

class Application(tornado.web.Application):

    def __init__(self, urls, config=None, **kwargs):

        if config:
            self.config = config
        else:
            self.config = self.process_config()

        cookie_secret = kwargs.pop('cookie_secret', None)
        if cookie_secret is None:
            cookie_secret = self.config['general'].get('cookie_secret', None)

        super(Application, self).__init__(urls, debug=self.config['general'].getboolean('debug'),
                                          cookie_secret=cookie_secret, **kwargs)

        self.asyncio_loop = asyncio.get_event_loop()
        if 'database' in self.config:
            from .database import prepare_database
            self.connection_pool = self.asyncio_loop.run_until_complete(
                prepare_database(self.config['database']))
        else:
            self.connection_pool = None

        if 'redis' in self.config:
            from .redis import prepare_redis
            self.redis_connection_pool = prepare_redis(self.config['redis'])

        max_workers = self.config['executor']['max_workers'] \
                      if 'executor' in self.config and 'max_workers' in self.config['executor'] \
                      else None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def process_config(self):

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

        if 'REDIS_URL' in os.environ:
            config['redis'] = {'url': os.environ['REDIS_URL']}

        if 'EXECUTOR_MAX_WORKERS' in os.environ:
            config['executor'] = {'max_workers': os.environ['EXECUTOR_MAX_WORKERS']}

        if 'COOKIE_SECRET' in os.environ:
            config['general']['cookie_secret'] = os.environ['COOKIE_SECRET']

        if 'SLACK_LOG_URL' in os.environ:
            config.setdefault('logging', SectionProxy(config, 'logging'))['slack_webhook_url'] = os.environ['SLACK_LOG_URL']
        if 'logging' in config and 'slack_webhook_url' in config['logging']:
            if 'SLACK_LOG_USERNAME' in os.environ:
                config['logging']['slack_log_username'] = os.environ['SLACK_LOG_USERNAME']
            if 'SLACK_LOG_LEVEL' in os.environ:
                config['logging']['slack_log_level'] = os.environ['SLACK_LOG_LEVEL']
            handler = SlackLogHandler(config['logging'].get('slack_log_username', None),
                                      {'default': config['logging']['slack_webhook_url']},
                                      level=config['logging'].get('slack_log_level', None))
            log.addHandler(handler)

        if 'LOG_LEVEL' in os.environ:
            config.setdefault('logging', SectionProxy(config, 'logging'))['level'] = os.environ['LOG_LEVEL']

        if 'logging' in config and 'level' in config['logging']:
            level = getattr(logging, config['logging']['level'].upper(), None)
            if level:
                log.setLevel(level)
            else:
                log.warning("log level is set in config but does not match one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`")

        # configure default torando loggers
        configure_logger(app_log)
        configure_logger(gen_log)
        configure_logger(access_log)

        return config

    def start(self):
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
