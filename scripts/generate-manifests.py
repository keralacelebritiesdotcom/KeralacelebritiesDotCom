from html.parser import HTMLParser
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
CELEB_DIR = ROOT / "celebrities"
MOVIE_DIR = ROOT / "movies"

CATEGORY_FILES = {"actors.html","directors.html","singers.html","television.html","other-personalities.html","index.html"}

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h1 = ""
        self.description = ""
        self.og_image = ""
        self.job_title = ""
        self.category = ""
        self.movie_status = ""
        self._tag = None
        self._buf = []
        self._jsonld = []
        self._in_jsonld = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._tag = tag
        if tag == "title": self._buf = []
        if tag == "h1": self._buf = []
        if tag == "meta":
            name = (a.get("name") or "").lower()
            prop = (a.get("property") or "").lower()
            content = a.get("content") or ""
            if name == "description": self.description = content
            elif prop == "og:image": self.og_image = content
            elif name == "celebrity-category": self.category = content
            elif name == "movie-status": self.movie_status = content
        if tag == "span" and "movie-status" in (a.get("class") or "").split():
            self._tag = "movie-status"
            self._buf = []
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._buf = []
    def handle_endtag(self, tag):
        if tag == "title" and self._buf: self.title = " ".join(self._buf).strip()
        elif tag == "h1" and self._buf: self.h1 = " ".join(self._buf).strip()
        elif tag == "movie-status" and self._buf and not self.movie_status: self.movie_status = " ".join(self._buf).strip()
        elif tag == "script" and self._in_jsonld:
            self._jsonld.append("".join(self._buf))
            self._in_jsonld = False
        self._tag = None
        if tag in ("title","h1"): self._buf = []
    def handle_data(self, data):
        if self._tag in ("title","h1") or self._in_jsonld:
            self._buf.append(data)


def clean_title(s):
    s = re.sub(r"\s*[|–—-]\s*KeralaCelebrities\.com.*$", "", s or "", flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def parse(path):
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    name = clean_title(parser.h1 or parser.title or path.stem.replace("-", " ").title())
    image = parser.og_image.strip() if parser.og_image else ""
    if image.startswith("https://keralacelebrities.com/"):
        image = image[len("https://keralacelebrities.com"):]
    if not image:
        image = f"/celebrities/images/{path.stem}.jpg"
    elif not image.startswith(("/", "http://", "https://")):
        image = "/celebrities/" + image.lstrip("./")
    categories = [c.strip().lower() for c in re.split(r"[,;]", parser.category) if c.strip()]
    if not categories:
        categories = ["actors"]
    description = parser.description or parser.job_title or "Kerala Celebrity"
    description = re.sub(r"\s+", " ", description).strip()
    return {"file": path.name, "name": name, "image": image, "description": description, "categories": categories}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    celebrities = []
    if CELEB_DIR.exists():
        for path in sorted(CELEB_DIR.glob("*.html")):
            if path.name.lower() in CATEGORY_FILES:
                continue
            try: celebrities.append(parse(path))
            except Exception as exc: print(f"Skipping {path}: {exc}")
    celebrities.sort(key=lambda x: x["name"].casefold())

    movies = []
    if MOVIE_DIR.exists():
        for path in sorted(MOVIE_DIR.glob("movie-*.html")):
            if not re.fullmatch(r"movie-\d+\.html", path.name, re.I):
                continue
            p = parse(path)
            m = re.search(r"movie-(\d+)", path.stem, re.I)
            number = int(m.group(1)) if m else 0
            movies.append({
                "file": path.name,
                "title": p["name"],
                "status": p.get("movie_status") or "Now Running",
                "image": p["image"] if p["image"] else f"/movies/images/movie-{number}.jpg"
            })

    write_json(ROOT / "celebrities.json", celebrities)
    write_json(ROOT / "movies.json", movies)
    print(f"Generated {len(celebrities)} celebrities and {len(movies)} movies")

if __name__ == "__main__": main()
