from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]

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
    """Extract a four-digit movie year from a movie title string."""
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
    """Return the movie title without its trailing year."""
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

    # IMPORTANT:
    # Check BOTH H1 and <title> for the year.
    # This fixes pages where H1 is "Bethlehem Kudumba Unit"
    # but <title> is "Bethlehem Kudumba Unit (2026) | KeralaCelebrities.com".
    h1_title = clean_title(parser.h1)
    page_title = clean_title(parser.title)

    year = (
        extract_movie_year(h1_title)
        or extract_movie_year(page_title)
    )

    # Prefer H1 as the clean movie name, but remove any year from it.
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


if __name__ == "__main__":
    main()
