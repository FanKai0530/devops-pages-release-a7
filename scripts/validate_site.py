"""Fail a Pages build when the README or rendered site's local links are broken."""

from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        target = values.get("href") if tag == "a" else values.get("src")
        if target:
            self.targets.append(target)


def validate(readme_path: Path, site_dir: Path):
    readme = readme_path.read_text(encoding="utf-8")
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain each activity marker exactly once")
    if readme.index(START) >= readme.index(END):
        raise ValueError("README activity markers are out of order")

    homepage = site_dir / "index.html"
    if not homepage.is_file():
        raise ValueError("Jekyll did not produce _site/index.html")
    rendered = homepage.read_text(encoding="utf-8")
    if "Recent activity" not in rendered:
        raise ValueError("README activity heading was not rendered on the homepage")

    links = Links()
    links.feed(rendered)
    failures = []
    for target in links.targets:
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith(("#", "//")):
            continue
        local_path = unquote(parsed.path)
        if not local_path:
            continue
        relative = local_path.lstrip("/") if local_path.startswith("/") else local_path
        candidate = site_dir / relative
        if target.startswith("/"):
            # Jekyll's project-site links may include the repository base path.
            prefix = "devops-pages-release-a7/"
            if relative.startswith(prefix):
                candidate = site_dir / relative[len(prefix):]
        if candidate.is_dir():
            candidate /= "index.html"
        if not candidate.is_file():
            failures.append(target)

    if failures:
        raise ValueError("Broken local links: " + ", ".join(failures))
    print(f"Validated README markers, rendered homepage and {len(links.targets)} links")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: validate_site.py README.md _site")
    try:
        validate(Path(sys.argv[1]), Path(sys.argv[2]))
    except ValueError as error:
        raise SystemExit(f"Release gate failed: {error}")

