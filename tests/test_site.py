from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.stylesheets: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if identifier := attributes.get("id"):
            self.ids.add(identifier)
        if tag == "link" and attributes.get("rel") == "stylesheet":
            if href := attributes.get("href"):
                self.stylesheets.add(href)


def test_project_site_has_complete_navigation_and_substantial_styles() -> None:
    parser = SiteParser()
    parser.feed((ROOT / "docs" / "index.html").read_text(encoding="utf-8"))

    assert {"top", "evaluate", "architecture", "compare", "safety"} <= parser.ids
    assert "site.css" in parser.stylesheets
    assert (ROOT / "docs" / "site.css").stat().st_size > 2_500
    assert (ROOT / "docs" / ".nojekyll").exists()


def test_project_site_uses_semantic_results_and_formatted_code() -> None:
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "docs" / "site.css").read_text(encoding="utf-8")

    assert 'class="code-window failed-window"' in html
    assert 'class="badge badge-danger"' in html
    assert 'class="key"' in html
    assert 'class="prompt"' in html
    assert "--green:" in css and "--amber:" in css and "--red:" in css
