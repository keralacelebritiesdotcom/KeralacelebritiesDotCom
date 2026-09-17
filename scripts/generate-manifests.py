from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape
import json
import re

ROOT = Path(__file__).resolve().parents[1]

SITE_URL = "https://keralacelebrities.com"

CELEB_DIR = ROOT / "celebrities"
CELEB_IMAGE_DIR = CELEB_DIR / "images"

MOVIE_DIR = ROOT / "movies"
MOVIE_IMAGE_DIR = MOVIE_DIR / "images"

CATEGORY_FILES = {
    "actors.html",
    "directors.html",
    "singers.html",
    "television.html",
    "other-personalities.html",
    "index.html",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.title = ""
        self.h1 = ""
        self.description = ""
        self.og_image = ""
        self.category = ""
        self.movie_status = ""

        self._tag = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._tag = tag

        if tag in ("title", "h1"):
            self._buf = []

        elif tag == "meta":
            name = (a.get("name") or "").lower()
            prop = (a.get("property") or "").lower()
            content = a.get("content") or ""

            if name == "description":
                self.description = content
            elif prop == "og:image":
                self.og_image = content
            elif name == "celebrity-category":
                self.category = content
            elif name == "movie-status":
                self.movie_status = content

        elif tag == "span" and "movie-status" in (a.get("class") or "").split():
            self._tag = "movie-status"
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "title" and self._buf:
            self.title = " ".join(self._buf).strip()

        elif tag == "h1" and self._buf:
            self.h1 = " ".join(self._buf).strip()

        elif tag == "span" and self._tag == "movie-status" and self._buf:
            if not self.movie_status:
                self.movie_status = " ".join(self._buf).strip()

        self._tag = None

        if tag in ("title", "h1"):
            self._buf = []

    def handle_data(self, data):
        if self._tag in ("title", "h1", "movie-status"):
            self._buf.append(data)


def clean_title(s):
    s = re.sub(
        r"\s*(?:\||–|—|-)\s*KeralaCelebrities\.com.*$",
        "",
        s or "",
        flags=re.I,
    )
    return re.sub(r"\s+", " ", s).strip()


def extract_movie_year(s):
    """
    Extract a four-digit movie year.

    Supports:
        Thudakkam (2026)
        Thudakkam – 2026
        Thudakkam - 2026
        Thudakkam 2026
    """
    s = clean_title(s)

    match = re.search(
        r"(?:\(\s*(\d{4})\s*\)|[–—-]\s*(\d{4})\s*)$",
        s,
    )

    if match:
        return int(next(group for group in match.groups() if group))

    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", s)

    return int(match.group(1)) if match else None


def remove_movie_year(s):
    """
    Remove a trailing movie year from the title.
    The year is stored separately in movies.json.
    """
    s = clean_title(s)

    s = re.sub(
        r"\s*\(\s*(?:19\d{2}|20\d{2}|21\d{2})\s*\)\s*$",
        "",
        s,
    )

    s = re.sub(
        r"\s*[–—-]\s*(?:19\d{2}|20\d{2}|21\d{2})\s*$",
        "",
        s,
    )

    return re.sub(r"\s+", " ", s).strip()


def normalise_image_url(image):
    image = (image or "").strip()

    for domain in (
        "https://keralacelebrities.com",
        "https://www.keralacelebrities.com",
    ):
        if image.startswith(domain):
            image = image[len(domain):]
            break

    return image


def find_matching_image(directory, stem):
    if not directory.exists():
        return ""

    target = stem.casefold()

    for image in directory.iterdir():
        if not image.is_file():
            continue
        if image.suffix.casefold() not in IMAGE_EXTENSIONS:
            continue
        if image.stem.casefold() == target:
            return image

    return ""


def image_url_for_file(image_path):
    return "/" + image_path.relative_to(ROOT).as_posix()


def parse_file(path):
    parser = PageParser()

    parser.feed(
        path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    )

    return parser


def parse_celebrity(path):
    parser = parse_file(path)

    name = clean_title(
        parser.h1
        or parser.title
        or path.stem.replace("-", " ").title()
    )

    matching_image = find_matching_image(
        CELEB_IMAGE_DIR,
        path.stem,
    )

    if matching_image:
        image = image_url_for_file(matching_image)
    else:
        image = normalise_image_url(parser.og_image)

        if image and not image.startswith(
            ("/", "http://", "https://")
        ):
            image = "/celebrities/" + image.lstrip("./")

    categories = [
        c.strip().lower()
        for c in re.split(r"[,;]", parser.category)
        if c.strip()
    ]

    if not categories:
        categories = ["actors"]

    description = re.sub(
        r"\s+",
        " ",
        parser.description or "Kerala Celebrity",
    ).strip()

    return {
        "file": path.name,
        "name": name,
        "image": image,
        "description": description,
        "categories": categories,
    }


def movie_number(path):
    match = re.fullmatch(
        r"movie-(\d+)\.html",
        path.name,
        re.I,
    )
    return int(match.group(1)) if match else 999999999


def parse_movie(path):
    parser = parse_file(path)

    # Check BOTH H1 and <title>.
    # Example:
    #   <h1>Bethlehem Kudumba Unit</h1>
    #   <title>Bethlehem Kudumba Unit (2026) | KeralaCelebrities.com</title>
    #
    # The year is therefore still found even when the H1 has no year.
    h1_title = clean_title(parser.h1)
    page_title = clean_title(parser.title)

    year = (
        extract_movie_year(h1_title)
        or extract_movie_year(page_title)
    )

    # Prefer the H1 for the clean movie name.
    raw_title = (
        h1_title
        or page_title
        or path.stem.replace("-", " ").title()
    )

    title = remove_movie_year(raw_title)

    image = normalise_image_url(parser.og_image)

    if image and not image.startswith(
        ("/", "http://", "https://")
    ):
        image = "/movies/" + image.lstrip("./")

    if not image:
        matching_image = find_matching_image(
            MOVIE_IMAGE_DIR,
            path.stem,
        )
        if matching_image:
            image = image_url_for_file(matching_image)

    status = parser.movie_status or "Now Showing"

    return {
        "file": path.name,
        "title": title,
        "year": year,
        "status": status,
        "image": image,
    }


def write_json(path, data):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def url_path_for_file(path):
    """
    Convert a repository HTML file into its public website URL.

    Examples:
        index.html
            -> /

        about.html
            -> /about.html

        celebrities/actors.html
            -> /celebrities/actors.html

        movies/movie-1.html
            -> /movies/movie-1.html
    """
    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":
        return "/"

    return "/" + relative



def public_url_for_file(path):
    return SITE_URL + url_path_for_file(path)


def has_jsonld_type(html, type_name):
    pattern = r'"@type"\s*:\s*"' + re.escape(type_name) + r'"'
    return re.search(pattern, html, flags=re.I) is not None


def extract_detail_value(html, label):
    pattern = (
        r'<div\s+class=["\']detail["\']\s*>\s*'
        r'<strong>\s*' + re.escape(label) + r'\s*</strong>\s*'
        r'<span>(.*?)</span>'
    )
    match = re.search(pattern, html, flags=re.I | re.S)
    if not match:
        return ""
    value = re.sub(r'<[^>]+>', ' ', match.group(1))
    return re.sub(r'\s+', ' ', unescape(value)).strip()


def build_celebrity_jsonld(path, parser):
    name = clean_title(parser.h1 or parser.title or path.stem.replace("-", " ").title())
    image = normalise_image_url(parser.og_image)
    if image and not image.startswith(("/", "http://", "https://")):
        image = "/celebrities/" + image.lstrip("./")
    if not image:
        matching_image = find_matching_image(CELEB_IMAGE_DIR, path.stem)
        if matching_image:
            image = image_url_for_file(matching_image)

    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": public_url_for_file(path) + "#person",
        "name": name,
        "url": public_url_for_file(path),
    }
    if image:
        data["image"] = SITE_URL + image if image.startswith("/") else image
    if parser.description:
        data["description"] = re.sub(r"\s+", " ", parser.description).strip()
    if parser.category:
        categories = [c.strip() for c in re.split(r"[,;]", parser.category) if c.strip()]
        if categories:
            data["jobTitle"] = categories
    return data


def build_movie_jsonld(path, parser):
    h1_title = clean_title(parser.h1)
    page_title = clean_title(parser.title)
    year = extract_movie_year(h1_title) or extract_movie_year(page_title)
    name = remove_movie_year(h1_title or page_title or path.stem.replace("-", " ").title())

    data = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "@id": public_url_for_file(path) + "#movie",
        "name": name,
        "url": public_url_for_file(path),
    }

    image = normalise_image_url(parser.og_image)
    if image and not image.startswith(("/", "http://", "https://")):
        image = "/movies/" + image.lstrip("./")
    if image:
        data["image"] = SITE_URL + image if image.startswith("/") else image

    if year:
        data["dateCreated"] = f"{year:04d}"

    director = extract_detail_value(
        path.read_text(encoding="utf-8", errors="ignore"),
        "Director",
    )
    if director:
        data["director"] = {"@type": "Person", "name": director}

    if parser.description:
        data["description"] = re.sub(r"\s+", " ", parser.description).strip()

    return data


def inject_structured_data(path, data, type_name):
    html = path.read_text(encoding="utf-8", errors="ignore")

    # Never create duplicate Person/Movie structured data on pages that already have it.
    if has_jsonld_type(html, type_name):
        return False

    marker = f"KERALA CELEBRITIES AUTO STRUCTURED DATA: {type_name}"
    block = (
        f'\n<!-- {marker} -->\n'
        '<script type="application/ld+json">\n'
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + '\n</script>\n'
        f'<!-- END {marker} -->\n'
    )

    if re.search(r"</head>\s*", html, flags=re.I):
        html = re.sub(r"</head>\s*", block + "</head>\n", html, count=1, flags=re.I)
        path.write_text(html, encoding="utf-8")
        return True

    return False


def generate_structured_data():
    added = 0
    skipped = 0

    if CELEB_DIR.exists():
        for path in CELEB_DIR.glob("*.html"):
            if path.name.lower() in CATEGORY_FILES:
                continue
            parser = parse_file(path)
            if inject_structured_data(path, build_celebrity_jsonld(path, parser), "Person"):
                added += 1
            else:
                skipped += 1

    if MOVIE_DIR.exists():
        for path in MOVIE_DIR.glob("movie-*.html"):
            if not re.fullmatch(r"movie-\d+\.html", path.name, re.I):
                continue
            parser = parse_file(path)
            if inject_structured_data(path, build_movie_jsonld(path, parser), "Movie"):
                added += 1
            else:
                skipped += 1

    print(f"Structured data: added {added} page(s); skipped {skipped} page(s) already containing the same type or without a usable </head>.")

def should_include_in_sitemap(path):
    """
    Include public HTML pages in sitemap.xml.

    The custom 404 page is excluded because it is not a
    content page users should find in search results.
    """

    if not path.is_file():
        return False

    if path.suffix.lower() != ".html":
        return False

    relative = path.relative_to(ROOT).as_posix()

    if relative == "404.html":
        return False

    # Ignore hidden/system directories such as .git and .github.
    parts = path.relative_to(ROOT).parts

    if any(part.startswith(".") for part in parts):
        return False

    return True


def generate_sitemap():
    """
    Automatically generate sitemap.xml from all public HTML
    pages in the repository.

    New HTML pages are picked up automatically on the next
    GitHub Actions run.
    """

    pages = []

    for path in ROOT.rglob("*.html"):
        if should_include_in_sitemap(path):
            pages.append(path)

    pages.sort(
        key=lambda path: url_path_for_file(path).casefold()
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path in pages:
        url_path = url_path_for_file(path)

        encoded_path = quote(
            url_path,
            safe="/:@-._~!$&'()*+,;="
        )

        full_url = SITE_URL + encoded_path

        lines.extend([
            "  <url>",
            f"    <loc>{escape(full_url)}</loc>",
            "  </url>",
        ])

    lines.append("</urlset>")

    sitemap_path = ROOT / "sitemap.xml"

    sitemap_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated sitemap.xml with {len(pages)} URLs."
    )


def generate_robots():
    """
    Automatically generate the root robots.txt file.
    """

    robots = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""

    robots_path = ROOT / "robots.txt"

    robots_path.write_text(
        robots,
        encoding="utf-8",
    )

    print("Generated robots.txt.")


def main():
    celebrities = []

    if CELEB_DIR.exists():
        for path in CELEB_DIR.glob("*.html"):
            if path.name.lower() in CATEGORY_FILES:
                continue

            try:
                celebrities.append(parse_celebrity(path))
            except Exception as exc:
                print(f"Skipping celebrity {path}: {exc}")

    celebrities.sort(
        key=lambda x: x["name"].casefold()
    )

    movies = []

    if MOVIE_DIR.exists():
        for path in MOVIE_DIR.glob("movie-*.html"):
            if not re.fullmatch(
                r"movie-\d+\.html",
                path.name,
                re.I,
            ):
                continue

            try:
                movies.append(parse_movie(path))
            except Exception as exc:
                print(f"Skipping movie {path}: {exc}")

    # IMPORTANT: numeric order, not alphabetical order.
    # This gives movie-1, movie-2, ..., movie-10.
    movies.sort(
        key=lambda x: movie_number(
            MOVIE_DIR / x["file"]
        )
    )

    write_json(
        ROOT / "celebrities.json",
        celebrities,
    )

    write_json(
        ROOT / "movies.json",
        movies,
    )

    print(
        f"Generated {len(celebrities)} celebrities "
        f"and {len(movies)} movies."
    )

    # SEO files are generated automatically.
    generate_structured_data()
    generate_sitemap()
    generate_robots()


if __name__ == "__main__":
    main()
