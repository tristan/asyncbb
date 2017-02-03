import asyncio
import testing.postgresql
from asyncbb.database import prepare_database

POSTGRESQL_FACTORY = testing.postgresql.PostgresqlFactory(cache_initialized_db=True)

def requires_database(func=None):
    """Used to ensure all database connections are returned to the pool
    before finishing the test"""
    def wrap(fn):

        async def wrapper(self, *args, **kwargs):

            psql = POSTGRESQL_FACTORY()
            self.pool = self._app.connection_pool = await prepare_database(psql.dsn())

            try:
                f = fn(self, *args, **kwargs)
                if asyncio.iscoroutine(f):
                    await f

                # wait for all the connections to be released
                while self._app.connection_pool._con_count != self._app.connection_pool._queue.qsize():
                    # if there are connections still in use, there should be some
                    # other things awaiting to be run. this simply pass control back
                    # to the ioloop to continue execution, looping until all the
                    # connections are released.
                    future = asyncio.Future()
                    self.io_loop.add_callback(lambda: future.set_result(True))
                    await future
            finally:
                psql.stop()

        return wrapper

    if func is not None:
        return wrap(func)
    else:
        return wrap
