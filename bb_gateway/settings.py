import os
import logging.config
import sentry_sdk
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster


load_dotenv()


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOGLEVEL', 'INFO'),
    },
})


ENV_SERVICE_PREFIX = 'SERVICE_'
SERVICE_URLS = {key.removeprefix(ENV_SERVICE_PREFIX).lower().replace('_', '-'): value for key, value in os.environ.items() if key.startswith(ENV_SERVICE_PREFIX)}
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', 1.0))

REDIS_TIMEOUT_GET = int(os.getenv('REDIS_TIMEOUT_GET', 15)) / 1000
REDIS_TIMEOUT_SET = int(os.getenv('REDIS_TIMEOUT_SET', 50)) / 1000
REDIS_CONNECT_TIMEOUT = int(os.getenv('REDIS_CONNECT_TIMEOUT', 10000)) / 1000
REDIS_DEFAULT = 'redis://localhost:6379/0'
REDIS_URL = os.getenv('REDIS_URL', REDIS_DEFAULT)
if REDIS_URL != REDIS_DEFAULT or os.getenv('REDIS_CLUSTER'):
    REDIS_CONN = RedisCluster.from_url(url=REDIS_URL, socket_connect_timeout=REDIS_CONNECT_TIMEOUT)

else:
    REDIS_CONN = Redis.from_url(REDIS_URL, socket_connect_timeout=REDIS_CONNECT_TIMEOUT)


def sentry_traces_sampler(context):
    if 'asgi_scope' in context and context['asgi_scope']['path'] == '/':
        return 0

    return SENTRY_TRACES_SAMPLE_RATE


sentry_sdk.init(
    environment=os.getenv('SENTRY_ENVIRONMENT', 'development'),
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[],
    traces_sampler=sentry_traces_sampler,
    send_default_pii=True,
    auto_session_tracking=True,
)
