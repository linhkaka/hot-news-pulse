"""HTTP helpers shared by the API clients."""

import threading

import requests


class ThreadSessions:
    """Drop-in for requests.Session that keeps one session per thread.

    Scans run in a thread pool and requests.Session is not guaranteed to be
    thread-safe, so each worker thread gets its own connection pool.
    """

    def __init__(self):
        self._local = threading.local()

    def _session(self):
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = requests.Session()
        return session

    def get(self, *args, **kwargs):
        return self._session().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self._session().post(*args, **kwargs)
