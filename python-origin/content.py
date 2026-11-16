"""Public catalog processing ported from src/router.js; edge owns auth and links."""
import re
from urllib.parse import unquote


class ContentError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def number(value, default=0, maximum=10000):
    if value in (None, ""):
        return default
    try:
        result = float(value)
        if not result.is_integer() or result < 0 or result > maximum:
            raise ValueError()
        return int(result)
    except (ValueError, TypeError, OverflowError):
        raise ContentError("Invalid numeric parameter: " + str(value)) from None


def anime(item):
    return bool(re.search("anime|animation", (item.get("genre") or "") + " " + ",".join(item.get("genres") or []), re.I))


def seasons(data):
    result = []
    for s in data.get("seasons") or []:
        season = int(s.get("se", s.get("season", 1)))
        raw = s.get("episodes")
        if raw is None:
            raw = str(s["allEp"]).split(",") if s.get("allEp") else list(range(1, int(s.get("maxEp") or 0) + 1))
        episodes = [{**e, "episode": int(e.get("ep") or e.get("episode")),
                     "title": e.get("title") or None, "description": e.get("description") or None}
                    if isinstance(e, dict) else {"episode": int(e), "title": None, "description": None} for e in raw]
        result.append({"season": season, "title": s.get("title") or f"Season {season}",
                       "totalEpisodes": int(s.get("maxEp") or len(raw)), "episodes": episodes,
                       "resolutions": s.get("resolutions") or []})
    return result


def dispatch(service, path, query):
    get = lambda name: query.get(name)
    p = {"page": number(get("page"), 1), "perPage": number(get("perPage"), 20, 100),
         "type": number(get("type"), 0, 2), "season": number(get("season") or get("se")),
         "episode": number(get("episode") or get("ep"))}
    if not p["page"] or not p["perPage"]:
        raise ContentError("page and perPage must be greater than zero")
    tail = [unquote(x) for x in path.removeprefix("/api/v3/").split("/")]
    is_anime = tail[0] == "anime"
    if is_anime and len(tail) > 1:
        tail.pop(0)
    action = tail[0]
    source = False
    direct = False
    if action == "homepage":
        result = service.call("home", {})
    elif action in {"trending", "anime"}:
        home = service.call("home", {})
        items = {}
        for section in home.get("operatingList") or home.get("items") or []:
            rows = list(section.get("subjects") or [])
            rows.extend(b.get("subject") or b for b in (section.get("banner") or {}).get("items") or [])
            for row in rows:
                if row.get("subjectId"):
                    items[str(row["subjectId"])] = service.normalize(row)
        rows = list(items.values())
        if action == "anime":
            rows = [row for row in rows if anime(row)]
        if p["type"]:
            rows = [row for row in rows if row.get("subjectType") == p["type"]]
        offset = (p["page"] - 1) * p["perPage"]
        result = {"items": rows[offset:offset+p["perPage"]], "total": len(rows), "page": p["page"],
                  "perPage": p["perPage"], "hasMore": offset+p["perPage"] < len(rows)}
    elif action == "search":
        p["query"] = tail[1].strip() if len(tail) > 1 else ""
        if not p["query"]:
            raise ContentError("Search query required")
        result = service.call("search", p)
        if is_anime:
            result["items"] = [row for row in result["items"] if anime(row)]
        if p["type"]:
            result["items"] = [row for row in result["items"] if row.get("subjectType") == p["type"]]
    elif action == "filter":
        p.update({name: get(name) for name in ["sort", "genre", "country", "year", "language"]})
        result = service.call("filter", p)
        result = {**result, "items": [service.normalize(row) for row in result.get("items") or result.get("subjects") or []]}
    elif action in {"info", "episodes", "season", "sources", "captions"}:
        p["id"] = tail[1] if len(tail) > 1 else ""
        if not re.fullmatch(r"\d{5,30}", p["id"]):
            raise ContentError("A numeric MovieBox subject ID is required")
        if is_anime and not anime(service.call("info", p)):
            raise ContentError("This title is not in the Anime/Animation genre", 404)
        if action in {"episodes", "season"}:
            data = service.call("episodes", p)
            rows = seasons(data)
            direct = True
            if action == "episodes":
                result = {"title": data.get("title"), "seasons": rows,
                          "totalEpisodes": sum(len(s["episodes"]) for s in rows)}
            else:
                selected = next((s for s in rows if s["season"] == number(tail[2] if len(tail) > 2 else None, 1)), None)
                if not selected:
                    raise ContentError("Season not found", 404)
                result = {"title": data.get("title"), "season": selected["season"],
                          "seasonTitle": selected["title"], "episodes": selected["episodes"]}
        else:
            if action == "captions":
                p["streamId"] = tail[2] if len(tail) > 2 else ""
                if not re.fullmatch(r"\d+", p["streamId"]):
                    raise ContentError("A numeric stream ID is required")
            result = service.call(action, p)
            if action == "captions" and get("format"):
                result = [r for r in result if r.get("url", "").split("?")[0].lower().endswith("." + get("format").lower())]
            source = action == "sources"
    elif action == "football":
        p["id"] = tail[1] if len(tail) > 1 else None
        name = "football-sources" if len(tail) > 2 and tail[2] == "sources" else "football-info" if p["id"] else "football"
        result = service.call(name, p)
        source = name == "football-sources"
        if not source:
            for row in result.get("items", [result]):
                row.pop("playPath", None)
                row.pop("playSource", None)
    else:
        raise ContentError("Endpoint not found", 404)
    return {"kind": "sources" if source else "direct" if direct else "results", "data": result, "params": p}
