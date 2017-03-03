import logging
import tornado.httpclient
import urllib

logging.basicConfig()
log = logging.getLogger("asyncbb.log")

class SlackLogHandler(logging.Handler):
    """A logging handler that sends error messages to slack"""
    def __init__(self, name, endpoints, level=None, client_class=tornado.httpclient.AsyncHTTPClient):
        logging.Handler.__init__(self)
        self.name = name
        if isinstance(endpoints, dict):
            default = endpoints['default'] if 'default' in endpoints else None
            debug = endpoints['debug'] if 'debug' in endpoints else default
            info = endpoints['info'] if 'info' in endpoints else default
            warning = endpoints['warning'] if 'warning' in endpoints else default
            error = endpoints['error'] if 'error' in endpoints else default
            critical = endpoints['critical'] if 'critical' in endpoints else default
        else:
            default = debug = info = warning = error = critical = endpoints
        self.endpoint_map = {
            logging.DEBUG: debug,
            logging.INFO: info,
            logging.WARNING: warning,
            logging.ERROR: error,
            logging.CRITICAL: critical
        }
        self.client_class = client_class
        self.min_level = level

    def emit(self, record):

        if self.min_level and record.levelno < self.min_level:
            return

        client = self.client_class()
        text = self.format(record)

        if record.levelno >= logging.ERROR: # error or critical
            icon = ":heavy_exclamation_mark:"
        elif record.levelno >= logging.WARNING: # warning
            icon = ":bangbang:"
        elif record.levelno >= logging.INFO:
            icon = ":sunny:"
        else: # debug
            icon = ":sparkles:"

        json = tornado.escape.json_encode(dict(
            text=text,
            unfurl_links=False,
            username=self.name,
            icon_url=icon
        ))
        body = urllib.parse.urlencode(dict(payload=json))
        endpoints = self.endpoint_map[record.levelno]
        if endpoints is None:
            return
        if not isinstance(endpoints, list):
            endpoints = [endpoints]
        for endpoint in endpoints:
            request = tornado.httpclient.HTTPRequest(endpoint, method="POST", headers=None, body=body)
            client.fetch(request)

def configure_logger(logger, send_to_slack=True):
    """Used to configure a new logger using the defaults
    loaded in the config"""

    logger.setLevel(log.level)
    if send_to_slack:
        for handler in log.handlers:
            if isinstance(handler, SlackLogHandler):
                logger.addHandler(handler)
