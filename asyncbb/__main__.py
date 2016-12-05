import asyncio
import sys
import tornado.platform
from .app import create_application, process_config, main

if __name__ == '__main__':
    # verify python version
    if sys.version_info[:2] != (3, 5):
        print("Requires python version 3.5")
        sys.exit(1)
    # install asyncio io loop (NOTE: must be done before app creation
    # as the autoreloader will also install one
    tornado.platform.asyncio.AsyncIOMainLoop().install()
    loop = asyncio.get_event_loop()
    config = process_config()
    app = loop.run_until_complete(create_application(config))
    main(app)
