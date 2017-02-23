import redis

def build_redis_url(**dsn):
    if 'unix_socket_path' in dsn and dsn['unix_socket_path'] is not None:
        if 'password' in dsn and dsn['password'] is not None:
            password = ':{}@'.format(dsn['password'])
        else:
            password = ''
        db = '?db={}'.format(dsn['db'] if 'db' in dsn and dsn['db'] is not None else 0)
        return 'unix://{}{}{}'.format(password, dsn['unix_socket_path'], db)
    elif 'url' in dsn:
        return dsn['url']
    raise NotImplementedError

def prepare_redis(config):
    if 'unix_socket_path' in config:
        redis_connection_pool = redis.ConnectionPool(
            connection_class=redis.connection.UnixDomainSocketConnection,
            decode_responses=True,
            password=config['password'] if 'password' in config else None,
            path=config['unix_socket_path'])
    elif 'url' in config:
        redis_connection_pool = redis.ConnectionPool.from_url(
            config['url'], decode_responses=True)
    else:
        redis_connection_pool = redis.ConnectionPool(
            decode_responses=True,
            **config)
    return redis_connection_pool

class RedisMixin:

    @property
    def redis(self):
        if not hasattr(self, '_redis'):
            self._redis = redis.StrictRedis(connection_pool=self.application.redis_connection_pool)
        return self._redis
