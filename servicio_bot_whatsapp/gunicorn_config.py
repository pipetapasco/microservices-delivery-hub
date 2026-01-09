"""Gunicorn configuration for production."""

import os

bind = f"0.0.0.0:{os.getenv('FLASK_RUN_PORT', 5000)}"

workers = int(os.getenv("GUNICORN_WORKERS", 1))

worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 4))

loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "-"
errorlog = "-"

timeout = 30
keepalive = 2

max_requests = 1000
max_requests_jitter = 50

preload_app = False

graceful_timeout = 30


def on_starting(server):
    """Called when Gunicorn master process starts."""
    pass


def when_ready(server):
    """Called when server is ready to accept connections."""
    pass


def worker_exit(server, worker):
    """Called when a worker exits."""
    from services.rabbitmq_service import close_all_connections
    from services.redis_client import close_redis_connection

    close_redis_connection()
    close_all_connections()
