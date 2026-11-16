"""Existing RosyScans selectors and response fields, moved from worker.js.

No third-party CORS bypass. Downloads use temporary disk files and bounded reads.
"""
import json
import re
import tempfile
import zipfile
from urllib.parse import urlencode, urljoin, urlsplit, unquote

from bs4 import BeautifulSoup
from curl_cffi import requests

SITE = "https://rosyscans.id"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36"


class MangaError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def slug(value):
    value = unquote(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise MangaError("Invalid manga slug", 400)
    return value


def safe_url(value):
    u = urlsplit(value)
    if u.scheme != "https" or u.hostname not in {"rosyscans.id", "img.rosyscans.id"} or u.username or u.password or u.port not in {None, 443}:
        raise MangaError("Manga host is not permitted", 400)
    return value


def fetch(value):
    current = safe_url(urljoin(SITE, value))
    for _ in range(5):
        response = requests.get(current, headers={"User-Agent": UA, "Referer": SITE},
                                timeout=20, stream=True, allow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise MangaError("Invalid manga redirect")
            current = safe_url(urljoin(current, location))
            continue
        if response.status_code != 200:
            response.close()
            raise MangaError("Manga provider is temporarily unavailable")
        return response
    raise MangaError("Too many manga redirects")


def page(path):
    response = fetch(path)
    try:
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > 5 * 1024 * 1024:
                raise MangaError("Manga page is too large")
        return BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
    finally:
        response.close()


def text(node, selector=None):
    nodes = node.select(selector) if selector else [node]
    return " ".join(" ".join(n.stripped_strings) for n in nodes).strip()


def attr(node, selector, key):
    item = node.select_one(selector)
    return (item.get(key) or "").strip() or None if item else None


def image(node):
    if node is None:
        return None
    img = node if node.name == "img" else node.select_one("img")
    return next((img.get(a).strip() for a in ("src", "data-src", "data-lazy-src") if img and img.get(a)), None)


def kind(node):
    el = node.select_one(".limit .type")
    value = " ".join(el.get("class", [])).replace("type", "").strip().lower() if el else ""
    return value if value in {"manga", "manhwa", "manhua"} else "unknown"


def card(node):
    return {"title": text(node, ".tt"), "url": attr(node, "a", "href"), "image": image(node),
            "chapter": text(node, ".epxs") or None, "type": kind(node)}


def listing(path, number):
    soup = page(path)
    return {"page": number, "hasNextPage": bool(soup.select(".hpage .r,.pagination .next,a.next.page-numbers")),
            "results": [card(n) for n in soup.select(".bsx")]}


def home():
    soup = page("/")
    data = {"popularToday": [card(n) for n in soup.select(".popularslider .bsx")],
            "projectUpdate": [], "latestUpdates": []}
    for box in soup.select(".bixbox"):
        section = text(box, ".releases h2")
        if section == "Project Update":
            for n in box.select(".bsx"):
                data["projectUpdate"].append({"title": text(n, ".tt a"), "url": attr(n, ".tt a", "href"),
                    "image": image(n), "type": kind(n), "chapters": [
                        {"chapter": text(ch, ".fivchap"), "timeUploaded": text(ch, ".fivtime"), "url": attr(ch, "a", "href")}
                        for ch in n.select(".chfiv li")]})
        if section == "Latest Update":
            for n in box.select(".uta"):
                data["latestUpdates"].append({"title": text(n, ".luf h4"), "url": attr(n, ".luf a.series", "href"),
                    "image": image(n.select_one(".imgu")), "chapters": [
                        {"chapter": text(ch, "a"), "timeUploaded": text(ch, "span"), "url": attr(ch, "a", "href")}
                        for ch in n.select(".luf ul li")]})
    return data


def details(value):
    target = SITE + "/manga/" + slug(value) + "/"
    soup = page(target)
    title_node = soup.select_one(".infox .entry-title,.postbody h1.entry-title")
    if not title_node or not text(title_node):
        raise MangaError("Could not parse manga details")
    def info(label):
        for row in soup.select(".imptdt,.infotable tr"):
            label_text = " ".join(str(x).strip() for x in row.find_all(string=True, recursive=False)).strip().lower()
            if label_text == label:
                value = row.select_one("i,a,b")
                return text(value) or None if value else None
        return None
    chapters = []
    for n in soup.select("#chapterlist li,.eplister li,.cl li"):
        label = text(n.select_one(".chapternum,.lchx a")) if n.select_one(".chapternum,.lchx a") else text(n, "a")
        if label:
            chapters.append({"chapter": label, "url": attr(n, "a", "href"),
                             "releaseDate": text(n, ".chapterdate,.dt") or None})
    return {"title": text(title_node), "url": target, "image": image(soup.select_one(".thumb img,.infoanime img")),
            "synopsis": text(soup, ".entry-content p") or None, "status": info("status"),
            "author": info("author"), "artist": info("artist"),
            "type": kind(soup.select_one(".infox") or soup),
            "genres": [text(n) for n in soup.select(".genxed a,.mgen a") if text(n)],
            "rating": text(soup.select_one(".rating strong,.num,.rating .rating-prc")) if soup.select_one(".rating strong,.num,.rating .rating-prc") else None,
            "chapters": chapters, "related": [card(n) for box in soup.select(".bixbox")
                if text(box, ".releases h2") == "Related Series" for n in box.select(".bsx")]}


def chapter(value):
    target = SITE + "/" + slug(value) + "/"
    soup = page(target)
    images = []
    for script in soup.select("script"):
        match = re.search(r"ts_reader\.run\((\{.*?\})\);", script.string or "", re.S)
        if match:
            try:
                payload = json.loads(match[1])
                sources = payload.get("sources") or []
                preferred = next((s for s in sources if s.get("source") == payload.get("defaultSource")), sources[0] if sources else {})
                images = preferred.get("images") or []
            except (ValueError, TypeError):
                pass
    if not images:
        images = [image(n) for n in soup.select("#readerarea img,.reading-content img,#readerchapter img") if image(n)]
    if not images:
        raise MangaError("No page images found for this chapter")
    title_node = soup.select_one(".entry-title,h1.entry-title")
    return {"chapterUrl": target, "title": text(title_node) if title_node else None, "images": images}


def archive(chapters, title):
    output = tempfile.TemporaryFile()
    total = 0
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as z:
            for prefix, images in chapters:
                for index, url in enumerate(images):
                    response = fetch(url)
                    ext = urlsplit(url).path.rsplit(".", 1)[-1].lower()
                    ext = ext if ext in {"jpg", "jpeg", "png", "webp", "gif", "avif"} else "jpg"
                    try:
                        if not response.headers.get("content-type", "").startswith("image/"):
                            raise MangaError("Manga provider returned non-image content")
                        with z.open(prefix + f"{index+1:03d}.{ext}", "w") as dest:
                            size = 0
                            for chunk in response.iter_content(chunk_size=65536):
                                size += len(chunk)
                                total += len(chunk)
                                if size > 20 * 1024 * 1024 or total > 256 * 1024 * 1024:
                                    raise MangaError("Manga archive exceeds download limit", 413)
                                dest.write(chunk)
                    finally:
                        response.close()
        output.seek(0)
        safe = re.sub(r"\s+", "-", re.sub(r"[^a-zA-Z0-9_ -]", "", title)).strip("-") or "chapter"
        return output, safe + ".zip"
    except Exception:
        output.close()
        raise


def dispatch(path, query):
    parts = path.removeprefix("/api/v3/manga/").strip("/").split("/")
    action = parts[0]
    get = lambda name, default="": (query.get(name) or [default])[0]
    try:
        number = max(1, int(get("page", "1")))
    except ValueError:
        number = 1
    if action == "home":
        return home()
    if action == "search":
        if not get("q").strip():
            raise MangaError("Query param 'q' required", 400)
        soup = page("/?" + urlencode({"s": get("q").strip()}))
        return [card(n) for n in soup.select(".postbody .listupd .bsx")]
    if action == "genres":
        soup, results, seen = page("/"), [], set()
        for n in soup.select(".genre a,.genrez li a,a[href*='/genres/']"):
            url, name = n.get("href"), text(n)
            value = url.rstrip("/").split("/")[-1] if url else None
            if value and name and value not in seen:
                seen.add(value)
                results.append({"name": name, "slug": value, "url": url})
        return results
    if action in {"latest", "popular", "browse"}:
        filters = []
        for key, allowed in {"status": ["ongoing", "completed", "hiatus"],
                              "type": ["manga", "manhwa", "manhua", "comic", "novel"],
                              "order": ["title", "titlereverse", "update", "latest", "popular"]}.items():
            if get(key):
                if get(key) not in allowed:
                    raise MangaError(f"Invalid {key}", 400)
                filters.append((key, get(key)))
        if action != "browse":
            filters = [("order", "update" if action == "latest" else "popular")]
        filters += [("genre[]", slug(x)) for x in query.get("genre", [])]
        return listing(("/manga/" if number == 1 else f"/manga/page/{number}/") + "?" + urlencode(filters), number)
    if len(parts) < 2:
        raise MangaError("Endpoint not found", 404)
    value = slug(parts[1])
    if action == "genre":
        return listing(f"/genres/{value}/" + (f"page/{number}/" if number > 1 else ""), number)
    if action == "details":
        return details(value)
    if action == "chapter":
        result = chapter(value)
        if len(parts) > 2 and parts[2] == "download":
            return archive([("", result["images"][:30])], result["title"] or value)
        return result
    if action == "download":
        result = details(value)
        try:
            start = max(1, int(get("from", "1")))
            end = min(start + 2, int(get("to", str(start + 2))))
        except ValueError:
            raise MangaError("Invalid chapter range", 400) from None
        selected = list(reversed(result["chapters"]))[start-1:end]
        if not selected:
            raise MangaError("No chapters in range", 404)
        chapters = []
        for offset, item in enumerate(selected):
            chapter_slug = (item.get("url") or "").rstrip("/").split("/")[-1]
            data = chapter(chapter_slug)
            chapters.append((f"chapter-{start+offset:03d}/", data["images"][:25]))
        return archive(chapters, f"{result['title']}-chapters-{start}-to-{end}")
    raise MangaError("Endpoint not found", 404)
