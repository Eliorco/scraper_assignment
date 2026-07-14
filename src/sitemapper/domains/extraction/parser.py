"""Deterministic HTML extraction for rendered pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from sitemapper.domains.crawling.models import RenderedPage
from sitemapper.domains.extraction.models import (
    LinkCandidate,
    PageContent,
    SectionCandidate,
)
from sitemapper.domains.extraction.url_tools import normalize_url

_LANDMARKS = frozenset({"nav", "main", "header", "footer", "aside"})
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    parent: _Node | None = None
    children: list[_Node] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    def text(self) -> str:
        pieces = [*self.text_parts, *(child.text() for child in self.children)]
        return " ".join(" ".join(pieces).split())


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(
            tag.lower(),
            {key.lower(): value or "" for key, value in attrs},
            self._stack[-1],
        )
        self._stack[-1].children.append(node)
        if tag.lower() not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._stack[-1].text_parts.append(data)


def _walk(node: _Node) -> list[_Node]:
    result: list[_Node] = []
    for child in node.children:
        result.append(child)
        result.extend(_walk(child))
    return result


def _landmark_role(node: _Node) -> str | None:
    role = node.attrs.get("role", "").lower()
    if role == "navigation":
        return "nav"
    if role in _LANDMARKS:
        return role
    return node.tag if node.tag in _LANDMARKS else None


def _nearest_role(node: _Node) -> str:
    current = node.parent
    while current is not None:
        role = _landmark_role(current)
        if role is not None:
            return role
        current = current.parent
    return "body"


def _section_label(node: _Node, role: str) -> str:
    label = node.attrs.get("aria-label", "").strip()
    if label:
        return label
    heading = next((item for item in _walk(node) if item.tag in {"h1", "h2", "h3"}), None)
    return heading.text() if heading is not None else role.capitalize()


def parse(rendered: RenderedPage) -> PageContent:
    """Parse rendered HTML and assign deterministic ``l{i}``/``s{i}`` candidate IDs."""

    parser = _TreeParser()
    parser.feed(rendered.html)
    nodes = _walk(parser.root)

    canonical_url = None
    for node in nodes:
        rel = node.attrs.get("rel", "").lower().split()
        if node.tag == "link" and "canonical" in rel:
            canonical_url = normalize_url(rendered.url, node.attrs.get("href", ""))
            break

    title_node = next((node for node in nodes if node.tag == "title"), None)
    title = title_node.text() if title_node and title_node.text() else rendered.title
    headings = [node.text() for node in nodes if node.tag in {f"h{i}" for i in range(1, 7)}]
    headings = [heading for heading in headings if heading]

    links: list[LinkCandidate] = []
    for node in nodes:
        if node.tag != "a":
            continue
        normalized = normalize_url(rendered.url, node.attrs.get("href", ""))
        if normalized is None:
            continue
        links.append(
            LinkCandidate(
                id=f"l{len(links)}",
                url=normalized,
                normalized_url=normalized,
                anchor_text=node.text(),
                section_role=_nearest_role(node),
            )
        )

    sections: list[SectionCandidate] = []
    for node in nodes:
        role = _landmark_role(node)
        if role is None:
            continue
        sample_links = [
            normalized
            for descendant in _walk(node)
            if descendant.tag == "a"
            and (normalized := normalize_url(rendered.url, descendant.attrs.get("href", "")))
            is not None
        ][:5]
        sections.append(
            SectionCandidate(
                id=f"s{len(sections)}",
                role=role,
                label=_section_label(node, role),
                sample_links=sample_links,
            )
        )

    return PageContent(
        url=rendered.url,
        title=title,
        headings=headings,
        canonical_url=canonical_url,
        links=links,
        sections=sections,
    )
