"""Python adapter of the user-supplied moviebox-final.js engine.

No substitute provider, generated catalog, or geographic bypass is used.
The existing server.py service owns web fallbacks and response normalization.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

from curl_cffi import requests

NATIVE_API_BASE = "https://api3.aoneroom.com"
BOOTSTRAP_HOST = "https://apig.inmoviebox.com"
WEB_USER_AGENT = "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36"
NATIVE_UA = "com.community.mbox.in/50020130 (Linux; U; Android 14; en_IN; Pixel 8; Build/UD1A.230803.041; Cronet/145.0.7582.0)"
BOOTSTRAP_PATH = "/wefeed-mobile-bff/tab/ranking-list?tabId=0&categoryType=4516404531735022304&page=1&perPage=1"
WEB_HOST = "https://h5-api.aoneroom.com"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical(method, url, body, timestamp):
    parsed = urlsplit(url)
    pairs = sorted(filter(None, parsed.query.split("&")), key=lambda x: x.split("=")[0])
    path = parsed.path or "/"
    if pairs:
        path += "?" + "&".join(pairs)
    raw = body.encode() if body is not None else b""
    return "\n".join([method.upper(), "application/json", "application/json",
                      str(len(raw)) if raw else "", str(timestamp),
                      hashlib.md5(raw[:102400]).hexdigest() if raw else "", path])


def stream_id(item):
    return str(item.get("id") or item.get("streamId") or item.get("resourceId") or "")


def unwrap(response):
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or str(payload.get("code", 0)) not in {"0", "200"}:
        raise RuntimeError("MovieBox rejected the request")
    return payload


class MovieBoxEngine:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.device_id = secrets.token_hex(16)
        self.bearer_token = None
        self._local = threading.local()
        self._bootstrap_lock = threading.RLock()

    @property
    def session(self):
        # curl sessions are thread-local: concurrent FastAPI calls do not share handles.
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session(impersonate="chrome", timeout=15)
        return self._local.session

    def headers(self, method, url, body=None, token=None, timestamp=None):
        encoded = os.environ.get("MOVIEBOX_SIGNING_KEY_B64", "")
        if not encoded:
            raise RuntimeError("MOVIEBOX_SIGNING_KEY_B64 must be configured for native MovieBox requests")
        try:
            key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
        except ValueError:
            raise RuntimeError("MOVIEBOX_SIGNING_KEY_B64 is invalid") from None
        if not key:
            raise RuntimeError("MOVIEBOX_SIGNING_KEY_B64 is empty")
        ts = int(time.time() * 1000) if timestamp is None else timestamp
        ci = {"package_name": "com.community.mbox.in", "version_name": "4.0.03.0920.03",
              "version_code": 50020130, "os": "android", "os_version": "14",
              "device_id": self.device_id, "install_store": "official",
              "brand": "Google", "model": "Pixel 8", "system_language": "en",
              "net": "NETWORK_WIFI", "region": "IN", "timezone": "Asia/Calcutta", "sp_code": ""}
        signature = base64.b64encode(hmac.new(key, canonical(method, url, body, ts).encode(), hashlib.md5).digest()).decode()
        headers = {"User-Agent": NATIVE_UA, "Accept": "application/json",
                   "Content-Type": "application/json", "x-client-info": compact(ci),
                   "x-client-status": "0",
                   "x-client-token": f"{ts},{hashlib.md5(str(ts)[::-1].encode()).hexdigest()}",
                   "x-tr-signature": f"{ts}|2|{signature}"}
        if token:
            headers["Authorization"] = "Bearer " + token
        return headers

    def bootstrap_token(self, force=False):
        with self._bootstrap_lock:
            if self.bearer_token and not force:
                return self.bearer_token
            for host in (BOOTSTRAP_HOST, NATIVE_API_BASE):
                url = host + BOOTSTRAP_PATH
                response = self.session.get(url, headers=self.headers("GET", url), allow_redirects=False)
                try:
                    if response.status_code == 200:
                        token = json.loads(response.headers.get("x-user", "{}")).get("token")
                        if token:
                            self.bearer_token = token
                            return token
                finally:
                    response.close()
            raise RuntimeError("MovieBox session unavailable")

    def api_request(self, method, path_or_url, body_dict=None, use_token=True, retry_auth=True):
        url = path_or_url if path_or_url.startswith("https://") else NATIVE_API_BASE + path_or_url
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {"api3.aoneroom.com", "apig.inmoviebox.com"}:
            raise ValueError("Unsupported MovieBox API host")
        if use_token and not self.bearer_token:
            self.bootstrap_token()
        body = compact(body_dict) if body_dict is not None else None
        response = self.session.request(method, url, data=body.encode() if body is not None else None,
                                        headers=self.headers(method, url, body, self.bearer_token if use_token else None),
                                        allow_redirects=False)
        try:
            if use_token and retry_auth and response.status_code in {401, 441}:
                self.bootstrap_token(force=True)
                return self.api_request(method, path_or_url, body_dict, use_token, False)
            return unwrap(response)
        finally:
            response.close()

    @staticmethod
    def normalize(row):
        s = row.get("subject") if isinstance(row.get("subject"), dict) else row
        cover = s.get("cover")
        return {"subject_id": str(s.get("subjectId") or ""), "title": s.get("title"),
                "subject_type": s.get("subjectType"), "description": s.get("description"),
                "release_date": s.get("releaseDate"), "duration": s.get("duration"),
                "imdb_rating": s.get("imdbRatingValue"), "genre": s.get("genre"),
                "country": s.get("countryName"), "language": s.get("language"),
                "cover": cover.get("url") if isinstance(cover, dict) else cover,
                "detail_path": str(row.get("detailUrl") or s.get("detailUrl") or s.get("detailPath") or "").rstrip("/").split("/")[-1],
                "dubs": row.get("dubs") or row.get("audioTracks") or s.get("dubs") or s.get("audioTracks") or []}

    def search(self, query, page=1, per_page=20):
        data = self.api_request("POST", "/wefeed-mobile-bff/subject-api/search",
                                {"keyword": query, "page": page, "perPage": per_page}).get("data", {})
        return [self.normalize(x) for x in data.get("items") or data.get("list") or []]

    def get_details(self, subject_id):
        data = self.api_request("GET", "/wefeed-mobile-bff/subject-api/get?" + urlencode({"subjectId": subject_id})).get("data", {})
        return self.normalize(data)

    def get_episodes(self, subject_id):
        data = self.api_request("GET", "/wefeed-mobile-bff/subject-api/season-info?" + urlencode({"subjectId": subject_id})).get("data", {})
        return [{"season": s.get("se"), "episode_count": s.get("maxEp"), "resolutions": s.get("resolutions") or []}
                for s in data.get("seasons") or []]

    def get_streams(self, subject_id, season=0, episode=0, detail_path=None):
        if not detail_path:
            detail_path = self.get_details(subject_id).get("detail_path", "")
        token = self.bootstrap_token()
        query = {"subjectId": subject_id, "se": season, "ep": episode, "detailPath": detail_path,
                 "streamSignType": 1, "supportCodecs[hevc]": 1, "supportCodecs[h264]": 1}
        streams, seen = [], set()

        def add(row, fmt, native=False):
            url = row.get("url")
            if not url or url in seen:
                return
            # Keep the provider's membership restriction; never report a paid source as free.
            if row.get("requireMemberType") not in (None, 0, "0"):
                return
            seen.add(url)
            resolution = str(row.get("resolutions") or "Adaptive")
            quality = next((n for n in (2160, 1440, 1080, 720, 480, 360, 240) if str(n) in resolution), 0)
            headers = {"User-Agent": NATIVE_UA if native else WEB_USER_AGENT,
                       "Referer": NATIVE_API_BASE + "/" if native else "https://moviebox.ph/"}
            if row.get("signCookie"):
                headers["Cookie"] = row["signCookie"]
            streams.append({"id": stream_id(row), "url": url, "format": row.get("format") or fmt,
                            "quality": f"{quality}p" if quality else resolution, "quality_value": quality,
                            "size_bytes": row.get("size"), "duration_sec": row.get("duration"),
                            "codec": row.get("codecName"), "headers": headers})
        try:
            response = self.session.get(WEB_HOST + "/wefeed-h5api-bff/subject/play?" + urlencode(query),
                                        headers={"User-Agent": WEB_USER_AGENT, "Referer": "https://moviebox.ph/",
                                                 "Authorization": "Bearer " + token, "Accept": "application/json"})
            try:
                data = unwrap(response).get("data") or {}
                for field, fmt in (("streams", "MP4"), ("dash", "DASH"), ("hls", "HLS")):
                    for row in data.get(field) or []:
                        add(row, fmt)
            finally:
                response.close()
        except Exception:
            # Native fallback below is the supplied engine's second source, not invented data.
            pass
        try:
            raw = self.api_request("GET", "/wefeed-mobile-bff/subject-api/play-info?" + urlencode(
                {"subjectId": subject_id, "se": season, "ep": episode})).get("data") or {}
            for row in raw.get("streams") or []:
                add(row, "MP4", True)
        except Exception:
            if not streams:
                raise
        return sorted(streams, key=lambda x: x["quality_value"], reverse=True)

    def get_subtitles(self, subject_id, stream=None, season=0, episode=0):
        if not stream:
            raw = self.api_request("GET", "/wefeed-mobile-bff/subject-api/play-info?" + urlencode(
                {"subjectId": subject_id, "se": season, "ep": episode})).get("data") or {}
            stream = next((stream_id(s) for s in raw.get("streams", []) if stream_id(s)), "")
        paths = ["/wefeed-mobile-bff/subject-api/get-ext-captions?" + urlencode(
            {"subjectId": subject_id, "resourceId": stream or "0", "episode": episode})]
        if stream:
            paths.insert(0, "/wefeed-mobile-bff/subject-api/get-stream-captions?" + urlencode(
                {"subjectId": subject_id, "streamId": stream}))
        result, seen, errors = [], set(), []
        for path in paths:
            try:
                data = self.api_request("GET", path).get("data") or {}
                rows = data if isinstance(data, list) else data.get("extCaptions") or data.get("captions") or []
                for row in rows:
                    url = row.get("url")
                    if url and url not in seen:
                        seen.add(url)
                        result.append({"id": str(row.get("id") or ""), "language": row.get("lanName") or row.get("language") or "English",
                                       "code": row.get("lan") or "", "url": url, "size": row.get("size")})
            except Exception as error:
                errors.append(error)
        if len(errors) == len(paths):
            raise RuntimeError("MovieBox captions unavailable")
        return result
