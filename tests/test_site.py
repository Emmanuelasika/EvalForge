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


def test_project_site_presents_an_interactive_evaluation_lab() -> None:
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "docs" / "site.css").read_text(encoding="utf-8")

    assert 'data-candidate="reference"' in html
    assert 'data-candidate="misrouted"' in html
    assert 'data-candidate="unsafe"' in html
    assert "RELEASE GATE BLOCKED" in html
    assert "evaluation-hero.webp" in html
    assert "evaluation-texture.webp" in html
    assert "--green:" in css and "--amber:" in css and "--red:" in css


def test_project_site_ships_its_original_visual_assets() -> None:
    assets = ROOT / "docs" / "assets"

    assert (assets / "evaluation-hero.webp").stat().st_size > 40_000
    assert (assets / "evaluation-texture.webp").stat().st_size > 40_000
