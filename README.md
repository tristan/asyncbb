# AsyncBB

framework for tornado/asyncpg based services

# Example application

`sql/create_tables.sql`
```
CREATE TABLE IF NOT EXISTS visitor_count (
    pk SERIAL PRIMARY KEY,
    count INTEGER DEFAULT 0
);

INSERT INTO visitor_count VALUES (1, 0) ON CONFLICT DO NOTHING;
```

`app.py`
```
import asyncbb.web
import asyncbb.handlers

class HelloHandler(asyncbb.handlers.BaseHandler):
    async def get(self):
        async with self.db:
            row = await self.db.fetchrow("UPDATE visitor_count SET count = count + 1 WHERE pk = 1 RETURNING count")
            await self.db.commit()
        self.write("<!DOCTYPE html><html><head><title>Hello World!</title></head><body>Welcome Visitor Number #{}</body></html>".format(row['count']))

urls = [
    (r"^/?$", HelloWorld
]

def main():
    app = asyncbb.web.Application(urls)
    app.start()

main()
```

Run: (NOTE: requires postgres is installed and running and there is a user and database for the current user)
```
python3 -m virtualenv env
env/bin/pip install git+https://github.com/tristan/asyncbb
DATABASE_URL=postgres://`whoami`@/`whoami` env/bin/python app.py
```

open http://localhost:8888

# Using Test base

## Additional pip requirements

```
testing.postgresql==1.3.0
```
