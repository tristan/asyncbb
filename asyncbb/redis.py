import redis

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
