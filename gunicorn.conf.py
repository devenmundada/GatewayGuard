"""Gunicorn settings (read automatically from the working directory)."""
import multiprocessing
import os
import shutil

from prometheus_client import multiprocess

bind = "0.0.0.0:8000"
worker_class = "uvicorn.workers.UvicornWorker"
# WEB_CONCURRENCY overrides; default 2 so small VMs are not starved (each worker also
# holds up to DB_POOL_SIZE+DB_MAX_OVERFLOW PostgreSQL connections).
workers = int(os.environ.get("WEB_CONCURRENCY", min(2, multiprocessing.cpu_count() * 2 + 1)))
timeout = 30
graceful_timeout = 20
keepalive = 5
accesslog = None  # LoggingMiddleware already logs every request as JSON
errorlog = "-"


def on_starting(server):
    """Start each container with an empty metrics directory (stale files = ghost series)."""
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path, exist_ok=True)


def child_exit(server, worker):
    """Tell prometheus_client a worker died so its gauges are cleaned up."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(worker.pid)
