import asyncio
import functools
import shutil
import uuid
import redis

from .processes import wait_for_start_line, shutdown_process

def gen_redis_config():
    """generates a redis config using a random unix socket"""
    socket_path = "/tmp/redis-testing.{}.sock".format(uuid.uuid4().hex)
    return {'unix_socket_path': socket_path, 'db': '1', 'password': 'testing'}

def start_redis(config=None, timeout=5):
    """Starts the testing redis server and returns the subprocess"""

    if config is None:
        config = gen_redis_config()
    redis_server_cmd = ["redis-server", "--unixsocket", config['unix_socket_path'], "--port", "0", "--loglevel", "warning"]
    if 'password' in config:
        redis_server_cmd.extend(["--requirepass", "testing"])

    process = wait_for_start_line(redis_server_cmd, "Server started")

    process._post_terminate_cleanup = functools.partial(shutil.rmtree, config['unix_socket_path'], ignore_errors=True)

    return process, config

def requires_redis(func=None):
    """Used to ensure all database connections are returned to the pool
    before finishing the test"""

    def wrap(fn):

        async def wrapper(self, *args, **kwargs):

            process, config = start_redis()

            self._app.config['redis'] = config

            self._app.redis_connection_pool = redis.ConnectionPool(
                connection_class=redis.connection.UnixDomainSocketConnection,
                decode_responses=True,
                password=config['password'] if 'password' in config else None,
                path=config['unix_socket_path'])

            self.redis = redis.StrictRedis(connection_pool=self._app.redis_connection_pool)

            try:
                f = fn(self, *args, **kwargs)
                if asyncio.iscoroutine(f):
                    await f
            finally:
                shutdown_process(process)

        return wrapper

    if func is not None:
        return wrap(func)
    else:
        return wrap
