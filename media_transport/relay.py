"""Private localhost media relay using Chrome-impersonating HTTP/2 transport.

Only accepts allowlisted MovieBox CDN URLs. It is intentionally bound to
127.0.0.1 and is not an internet-facing arbitrary URL proxy.
"""
import logging
import re
import threading
from urllib.parse import urljoin, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from .curl_transport import CurlStreamClient, MAX_STREAMS

ALLOWED_HOSTS = (
    "hakunaymatata.com", "aoneroom.com", "histar.tv", "cloudfront.net",
    "aisports.mobi", "aisports.cc", "moviebox.ph", "movieboxhd.net",
    "inmoviebox.com",
)
REDIRECTS = {301, 302, 303, 307, 308}
FORWARDED_HEADERS = {
    "accept-ranges", "cache-control", "content-length", "content-range",
    "content-type", "date", "etag", "expires", "last-modified",
}
slots = threading.BoundedSemaphore(MAX_STREAMS)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
logger = logging.getLogger("media_transport.relay")


def safe_url(value: str):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except (TypeError, ValueError):
        raise ValueError("Invalid media URL") from None
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
        or (port is not None and port != 443) or parsed.fragment
        or not any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOSTS)):
        raise ValueError("Media host is not permitted")
    return parsed


def safe_headers(value):
    if not isinstance(value, dict) or len(value) > 24:
        raise ValueError("Invalid media headers")
    forbidden = {"host", "authorization", "proxy-authorization", "connection",
                 "content-length", "transfer-encoding", "range", "accept-encoding"}
    result = {}
    for name, raw in value.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
            or name.lower() in forbidden or not isinstance(raw, str) or len(raw) > 4096
            or "\r" in raw or "\n" in raw):
            raise ValueError("Invalid media headers")
        # Preserve MovieBox's provider-specific signing headers (for example
        # X-MB-Token); dangerous hop-by-hop/auth headers remain blocked.
        result[name] = raw
    result.setdefault("User-Agent", "Mozilla/5.0")
    result["Accept-Encoding"] = "identity"
    return result


def open_upstream(method, url, headers, range_value, if_range_value=None):
    target = url
    current_headers = dict(headers)
    for _ in range(6):
        safe_url(target)
        if range_value:
            current_headers["Range"] = range_value
        if if_range_value:
            current_headers["If-Range"] = if_range_value
        client = CurlStreamClient()
        response = client.send(client.build_request(method, target, current_headers))
        if response.status_code in REDIRECTS:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise ValueError("Media redirect has no location")
            next_target = urljoin(target, location)
            previous_host = urlsplit(target).hostname
            next_host = urlsplit(next_target).hostname
            safe_url(next_target)
            if next_host != previous_host:
                current_headers = {k: v for k, v in current_headers.items()
                                   if k.lower() in {"user-agent", "referer", "origin", "accept", "accept-language"}}
            target = next_target
            continue
        return response
    raise ValueError("Too many media redirects")


@app.get("/health")
def health():
    return {"ok": True, "transport": "curl-cffi-http2", "capacity": MAX_STREAMS}


@app.post("/fetch")
async def fetch(request: Request):
    if not slots.acquire(blocking=False):
        return JSONResponse({"message": "Media relay is at capacity; retry shortly"}, status_code=503,
                            headers={"Retry-After": "5"})
    response = None
    try:
        payload = await request.json()
        url = payload.get("url")
        method = "HEAD" if payload.get("method") == "HEAD" else "GET"
        safe_url(url)
        headers = safe_headers(payload.get("headers", {}))
        range_value = request.headers.get("range")
        if range_value and (len(range_value) > 100 or not re.fullmatch(r"bytes=\d*-\d*", range_value)):
            raise ValueError("Only a single byte range is supported")
        if_range_value = request.headers.get("if-range")
        response = await run_in_threadpool(open_upstream, method, url, headers, range_value, if_range_value)
        out_headers = {k: v for k, v in response.headers.items() if k.lower() in FORWARDED_HEADERS}
        status = response.status_code
        if method == "HEAD":
            response.close()
            slots.release()
            response = None
            return Response(status_code=status, headers=out_headers)

        released = False
        def release():
            nonlocal released
            if not released:
                released = True
                response.close()
                slots.release()

        def body():
            try:
                yield from response.iter_raw()
            except Exception as exc:
                logger.error("media body interrupted host=%s error=%s", urlsplit(url).hostname or "unknown", type(exc).__name__)
                raise
            finally:
                release()

        return StreamingResponse(body(), status_code=status, headers=out_headers,
                                 background=BackgroundTask(release))
    except ValueError as exc:
        if response is not None:
            response.close()
        slots.release()
        # Include a safe diagnostic in Railway logs; never log signed URLs or headers.
        logger.warning("media request rejected: %s", str(exc)[:180])
        return JSONResponse({"message": str(exc), "code": "MEDIA_REQUEST_REJECTED"}, status_code=400)
    except Exception as exc:
        if response is not None:
            response.close()
        slots.release()
        host = "unknown"
        try:
            host = (urlsplit(payload.get("url", "")).hostname or "unknown")
        except Exception:
            pass
        logger.error("upstream media connection failed host=%s error=%s", host, type(exc).__name__)
        return JSONResponse({"message": "Upstream media connection failed", "code": "MEDIA_UPSTREAM_CONNECT_FAILED"}, status_code=502)
