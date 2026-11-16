"""Opt-in live provider smoke checks. Never logs signed URLs or credentials.

Run with RELAY_SECRET set. Native fallback additionally needs MOVIEBOX_SIGNING_KEY_B64.
Only bounded byte ranges are read; an upstream full-body response is closed immediately.
"""
import json
import server

results = {}


def check(name, fn):
    try:
        results[name] = fn()
    except Exception as error:
        results[name] = {"ok": False, "errorType": type(error).__name__}


def homepage():
    data = server.service.call("home", {})
    items = [i for section in data.get("operatingList", []) for i in section.get("subjects", [])]
    homepage.items = items
    return {"ok": bool(items), "sections": len(data.get("operatingList", [])), "titles": len(items)}


def details():
    item = next((i for i in homepage.items if i.get("subjectType") == 1), homepage.items[0])
    details.id = str(item["subjectId"])
    data = server.service.info(details.id)
    details.data = data
    return {"ok": bool(data.get("title") and data.get("thumbnail")), "title": data.get("title"),
            "descriptionPresent": bool(data.get("description")), "trailerPresent": bool(data.get("trailer"))}


def search():
    data = server.service.call("search", {"query": "Interstellar", "page": 1, "perPage": 5})
    return {"ok": bool(data.get("items")), "count": len(data.get("items", [])),
            "note": "An empty result does not verify search correctness"}


def media():
    data = server.service.call("sources", {"id": details.id})
    row = next(r for r in data["results"] if r.get("format", "").lower() == "mp4")
    server._safe_media_url(row["url"])
    checks = []
    for start in (0, 1048576):
        response = server._start_media(row["url"], server._media_headers(row.get("headers")),
                                       f"bytes={start}-{start+1023}", "GET")
        try:
            size = 0
            if response.status_code == 206:
                for chunk in response.iter_raw():
                    size += len(chunk)
                    if size > 1024:
                        break
            checks.append({"status": response.status_code, "bytes": size,
                           "range": response.headers.get("content-range")})
        finally:
            response.close()
    return {"ok": all(x["status"] == 206 and x["bytes"] == 1024 for x in checks), "ranges": checks}


check("homepage", homepage)
check("details", details)
check("search", search)
check("mediaRanges", media)
print(json.dumps(results, indent=2))
