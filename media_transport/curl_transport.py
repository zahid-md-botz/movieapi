"""Browser-compatible HTTP/2 transport adapted from the supplied MIT-licensed code."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from queue import Queue, Full, Empty
import threading
import time

from curl_cffi import Curl, CurlHttpVersion, CurlOpt
import httpx

MAX_STREAMS = 8
MAX_STREAM_QUEUE_CHUNKS = 8
_stream_executor = ThreadPoolExecutor(max_workers=MAX_STREAMS, thread_name_prefix="media-stream")
_stream_local = threading.local()


class CurlStreamClient:
    def build_request(self, method, url, headers):
        return method, url, headers

    def send(self, request, stream=True):
        return CurlStreamResponse(*request)

    def close(self):
        pass


class CurlStreamResponse:
    def __init__(self, method, url, headers):
        self.headers = httpx.Headers()
        self.status_code = 0
        self.queue = Queue(maxsize=MAX_STREAM_QUEUE_CHUNKS)
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.finished = threading.Event()
        self.error = None

        def header(data):
            line = data.decode("iso-8859-1").strip()
            if line.startswith("HTTP/"):
                self.status_code = int(line.split()[1])
                self.headers = httpx.Headers()
            elif ":" in line:
                key, value = line.split(":", 1)
                self.headers[key.strip()] = value.strip()
            elif not line and self.status_code >= 200:
                self.ready.set()
            return len(data)

        def write(data):
            while not self.stopped.is_set():
                try:
                    self.queue.put(data, timeout=0.2)
                    return len(data)
                except Full:
                    continue
            return 0

        def perform():
            curl = getattr(_stream_local, "curl", None)
            if curl is None:
                curl = Curl()
                _stream_local.curl = curl
            else:
                # A worker thread reuses its handle; reset method/options/callbacks
                # before each new request so a prior HEAD cannot poison the next GET.
                curl.reset()
            # Prefer the reference project's HTTP/2 path, then retry once over
            # HTTP/1.1. Some CDN edges return 421/425/426 when their first ALPN
            # negotiation lands on an edge that wants the other HTTP version;
            # those statuses are transport negotiation failures, not final media
            # decisions. Do not retry ordinary upstream responses such as 403.
                versions = (CurlHttpVersion.V2_0, CurlHttpVersion.V1_1, CurlHttpVersion.V2_0)
            try:
                for attempt, version in enumerate(versions):
                    if attempt:
                        curl.reset()
                        self.status_code = 0
                        self.headers = httpx.Headers()
                    try:
                        curl.impersonate("chrome")
                        curl.setopt(CurlOpt.HTTP_VERSION, version)
                        curl.setopt(CurlOpt.URL, url.encode())
                        curl.setopt(CurlOpt.HTTPHEADER, [f"{key}: {value}".encode() for key, value in headers.items()])
                        curl.setopt(CurlOpt.FOLLOWLOCATION, 0)
                        curl.setopt(CurlOpt.SUPPRESS_CONNECT_HEADERS, 1)
                        curl.setopt(CurlOpt.CONNECTTIMEOUT, 12)
                        curl.setopt(CurlOpt.LOW_SPEED_LIMIT, 1)
                        curl.setopt(CurlOpt.LOW_SPEED_TIME, 90)
                        curl.setopt(CurlOpt.HEADERFUNCTION, header)
                        curl.setopt(CurlOpt.WRITEFUNCTION, write)
                        if method == "HEAD":
                            curl.setopt(CurlOpt.NOBODY, 1)
                        curl.perform()
                        if self.status_code in {421, 425, 426, 429} and attempt < len(versions) - 1:
                            self.error = RuntimeError(f"Retrying media request after HTTP {self.status_code}")
                            if self.status_code == 429:
                                time.sleep(0.25)
                            continue
                        if self.status_code:
                            self.error = None
                            break
                        self.error = RuntimeError("No HTTP response headers received")
                    except Exception as error:
                        self.error = error
                        if self.status_code or attempt == len(versions) - 1:
                            break
            finally:
                self.finished.set()
                self.ready.set()

        self.future = _stream_executor.submit(perform)
        if not self.ready.wait(25) or not self.status_code:
            self.close()
            raise RuntimeError("Media connection failed")

    def iter_raw(self, size=65536):
        while not self.finished.is_set() or not self.queue.empty():
            try:
                yield self.queue.get(timeout=0.2)
            except Empty:
                continue
        if self.error and not self.stopped.is_set():
            raise RuntimeError("Media transfer interrupted") from None

    iter_bytes = iter_raw

    def close(self):
        self.stopped.set()
        try:
            self.future.result(timeout=1.5)
        except FutureTimeout:
            pass
