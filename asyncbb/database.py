import asyncio
import asyncpg
import os
from collections import ItemsView
from .errors import DatabaseError
from .log import log

class SafePool(asyncpg.pool.Pool):
    """changes the connection acquire implementation to deal with connections
    disconnecting when not in use"""

    async def _acquire_impl(self):
        while True:
            con = await super(SafePool, self)._acquire_impl()
            if con.is_closed():
                await self.release(con)
            else:
                return con

def create_pool(dsn=None, *,
                min_size=10,
                max_size=10,
                max_queries=50000,
                setup=None,
                loop=None,
                init=None,
                **connect_kwargs):
    if '_init' in asyncpg.pool.Pool.__slots__:
        connect_kwargs['init'] = init
    elif init is not None:
        raise DatabaseError("init only supported in asyncpg versions 0.9.0 and up")
    return SafePool(dsn,
                    min_size=min_size, max_size=max_size,
                    max_queries=max_queries, loop=loop, setup=setup,
                    **connect_kwargs)

async def prepare_database(db_config):

    connection_pool = await create_pool(**db_config)
    async with connection_pool.acquire() as con:
        await create_tables(con)

    return connection_pool

async def create_tables(con):

    # make sure the create tables script exists
    if not os.path.exists("sql/create_tables.sql"):
        log.warning("Missing sql/create_tables.sql: cannot initialise database")
        return

    try:
        row = await con.fetchrow("SELECT version_number FROM database_version LIMIT 1")
        version = row['version_number']
        log.info("got database version: {}".format(version))
    except asyncpg.exceptions.UndefinedTableError:

        # fresh DB path

        await con.execute("CREATE TABLE database_version (version_number INTEGER)")
        await con.execute("INSERT INTO database_version (version_number) VALUES (0)")

        # fresh database, nothing to migrate
        with open("sql/create_tables.sql") as create_tables_file:

            sql = create_tables_file.read()

            await con.execute(sql)

        # verify that if there are any migration scripts, that the
        # database_version table has been updated appropriately
        version = 0
        while True:
            version += 1
            if not os.path.exists("sql/migrate_{:08}.sql".format(version)):
                version -= 1
                break

        if version > 0:
            row = await con.fetchrow("SELECT version_number FROM database_version LIMIT 1")
            if row['version_number'] != version:
                log.warning("Warning, migration scripts exist but database version has not been set in create_tables.sql")
                log.warning("DB version: {}, latest migration script: {}".format(row['version_number'], version))

        return

    # check for migration files

    exception = None
    while True:
        version += 1

        fn = "sql/migrate_{:08}.sql".format(version)
        if os.path.exists(fn):
            log.info("applying migration script: {:08}".format(version))
            with open(fn) as migrate_file:
                sql = migrate_file.read()
                try:
                    await con.execute(sql)
                except Exception as e:
                    version -= 1
                    exception = e
                    break
        else:
            version -= 1
            break

    await con.execute("UPDATE database_version SET version_number = $1", version)
    if exception:
        raise exception

class HandlerDatabasePoolContext():

    __slots__ = ('timeout', 'handler', 'connection', 'transaction', 'autocommit', 'pool', 'done', 'callbacks')

    def __init__(self, handler, pool, autocommit=False, timeout=None):
        self.handler = handler
        self.pool = pool
        self.timeout = timeout
        self.autocommit = autocommit
        self.connection = None
        self.transaction = None
        self.done = False
        self.callbacks = []

    async def __aenter__(self):
        if self.connection is not None:
            raise DatabaseError("Connection already in progress")
        self.connection = await self.pool.acquire(timeout=self.timeout)
        self.transaction = self.connection.transaction()
        await self.transaction.start()
        return self.connection

    async def __aexit__(self, extype, ex, tb):
        try:
            if self.transaction:
                if extype is not None or self.autocommit is False:
                    await self.transaction.rollback()
                elif self.autocommit:
                    await self.commit()
        finally:
            con = self.connection
            self.transaction = None
            self.connection = None
            self.done = True
            await self.pool.release(con)

    async def commit(self, create_new_transaction=False):
        if self.transaction:
            try:
                callbacks = self.callbacks[:]
                self.callbacks.clear()
                rval = await self.transaction.commit()
                for callback in callbacks:
                    f = callback()
                    if asyncio.iscoroutine(f):
                        await f
                return rval
            finally:
                if create_new_transaction:
                    self.transaction = self.connection.transaction()
                    await self.transaction.start()
                else:
                    self.done = True
                    self.transaction = None
        else:
            raise DatabaseError("No transaction to commit")

    def on_commit(self, callback):
        """used to trigger functions on commit"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def execute(self, query: str, *args, timeout: float=None) -> str:
        if self.transaction:
            return self.connection.execute(query, *args, timeout=timeout)
        else:
            raise DatabaseError("No transaction in progress")

    def fetch(self, query, *args, timeout=None):
        if self.transaction:
            return self.connection.fetch(query, *args, timeout=timeout)
        else:
            raise DatabaseError("No transaction in progress")

    def fetchval(self, query, *args, column=0, timeout=None):
        if self.transaction:
            return self.connection.fetchval(query, *args, column=column, timeout=timeout)
        else:
            raise DatabaseError("No transaction in progress")

    def fetchrow(self, query, *args, timeout=None):
        if self.transaction:
            return self.connection.fetchrow(query, *args, timeout=timeout)
        else:
            raise DatabaseError("No transaction in progress")

    async def update(self, tablename, update_args, query_args=None):
        """Very simple "generic" update helper.
        will generate the update statement, converting the `update_args`
        dict into "key = value, key = value" statements, and converting
        the `query_args` dict into "key = value AND key = value"
        statements. string values will be wrapped in 'quotes', while
        other types will be left as their python representation.
        """

        if not self.transaction:
            raise DatabaseError("No transaction in progress")

        query = "UPDATE {} SET ".format(tablename)
        arglist = []
        qnum = 1
        if isinstance(update_args, dict):
            update_args = update_args.items()
        if isinstance(update_args, (list, tuple, ItemsView)):
            setstmts = []
            for k, v in update_args:
                setstmts.append("{} = ${}".format(k, qnum))
                qnum += 1
                arglist.append(v)
            query += ', '.join(setstmts)
        else:
            raise DatabaseError("expected dict or list for update_args")
        if isinstance(query_args, dict):
            query_args = query_args.items()
        if isinstance(query_args, (list, tuple, ItemsView)):
            query += " WHERE "
            wherestmts = []
            # TODO: support OR somehow?
            for k, v in query_args:
                wherestmts.append("{} = ${}".format(k, qnum))
                qnum += 1
                arglist.append(v)
            query += ' AND '.join(wherestmts)
        elif query_args is not None:
            raise DatabaseError("expected dict or list or None for query_args")

        resp = await self.connection.execute(query, *arglist)

        if resp and resp[0].startswith("ERROR:"):
            raise DatabaseError(resp)
        return resp

def with_database(fn):
    async def wrapper(self, *args, **kwargs):
        async with self.db:
            r = fn(self, *args, **kwargs)
            if asyncio.iscoroutine(r):
                r = await r
            return r
    return wrapper

class DatabaseMixin:
    @property
    def db(self):
        if not hasattr(self, '_dbcontext'):
            self._dbcontext = HandlerDatabasePoolContext(self, self.application.connection_pool)
        return self._dbcontext
