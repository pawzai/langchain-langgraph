"""Document ingestion: walk the knowledge directory, split each format appropriately, and
attach the metadata the retrieval and citation layers depend on.

Splitting is per-format on purpose. A rules document and a Java class fail in different ways
when you cut them at an arbitrary character count: the document loses the heading that gives a
rule its meaning, the class loses the method signature that gives a body its meaning.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.config import settings

HEADERS = [("#", "doc_title"), ("##", "section"), ("###", "subsection")]

CODE_LANGUAGES = {
    ".py": Language.PYTHON,
    ".java": Language.JAVA,
    ".ts": Language.TS,
    ".js": Language.JS,
}

TEXT_SUFFIXES = {".txt", ".text"}

SUPPORTED_SUFFIXES = {".md", ".pdf"} | TEXT_SUFFIXES | set(CODE_LANGUAGES)


def chunk_id(source: str, text: str, locator: str = "") -> str:
    """Stable identity for a chunk.

    Derived from content rather than position, so editing one section of a document does not
    renumber every chunk after it. That is what makes incremental indexing possible.

    The locator (heading, page) is folded in as well: it is displayed in citations, so a chunk
    whose heading changed is not the same stored chunk even though its text is byte-identical.
    Hashing text alone would leave stale labels in the index forever.
    """
    digest = hashlib.sha256(f"{source}\x00{locator}\x00{text}".encode("utf-8")).hexdigest()
    return digest[:16]


def _base_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def _load_markdown(path: Path, source: str) -> list[Document]:
    """Split on headings first, then on size.

    Heading-aware splitting keeps a rule and its conditions in one chunk, which matters here
    because the dispatch rules are written as short lists under a heading.
    """
    header_splitter = MarkdownHeaderTextSplitter(HEADERS, strip_headers=False)
    sections = header_splitter.split_text(path.read_text(encoding="utf-8"))
    for section in sections:
        section.metadata["source"] = source
    return _base_splitter().split_documents(sections)


def _load_pdf(path: Path, source: str) -> list[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    pages = PyPDFLoader(str(path)).load()
    for page in pages:
        # PyPDFLoader writes an absolute path into `source`; the relative one is what the
        # citation UI should show, and what the golden set matches against.
        page.metadata["source"] = source
        number = page.metadata.get("page", 0) + 1
        page.metadata["page"] = number
        # A PDF has no headings to split on, so the page number is the only locator a reader
        # can act on. Without it every citation from this file would look identical.
        page.metadata["section"] = f"page {number}"
    return _base_splitter().split_documents(pages)


def _load_text(path: Path, source: str) -> list[Document]:
    doc = Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": source})
    return _base_splitter().split_documents([doc])


def _load_code(path: Path, source: str, language: Language) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    doc = Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": source})
    return splitter.split_documents([doc])


def _load_one(path: Path, source: str) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return _load_markdown(path, source)
    if suffix == ".pdf":
        return _load_pdf(path, source)
    if suffix in CODE_LANGUAGES:
        return _load_code(path, source, CODE_LANGUAGES[suffix])
    if suffix in TEXT_SUFFIXES:
        return _load_text(path, source)
    return []


def _default_title(source: str) -> str:
    stem = Path(source).stem
    # Title-casing a snake_case filename reads well; doing it to a CamelCase class name does
    # not, so leave anything that already carries capitals alone.
    return stem.replace("_", " ").title() if stem == stem.lower() else stem


def _normalise(doc: Document, source: str, suffix: str) -> Document:
    """Guarantee every chunk carries the keys retrieval, fusion and citations rely on."""
    meta = doc.metadata
    meta["source"] = source
    meta["doc_type"] = suffix.lstrip(".")
    meta.setdefault("doc_title", _default_title(source))

    # Markdown carries real headings, so fall back through them to give a citation a locator
    # more specific than the filename. Code and plain text have none; for those the path is
    # the locator, and repeating it as a section would just make the label say it twice.
    if not meta.get("section"):
        meta["section"] = (
            meta.get("subsection") or meta.get("doc_title") or "" if suffix == ".md" else ""
        )

    locator = "|".join(
        str(meta.get(key, "")) for key in ("doc_title", "section", "subsection", "page")
    )
    meta["chunk_id"] = chunk_id(source, doc.page_content, locator)

    # Chroma rejects None and complex values in metadata, so flatten anything the loaders left.
    for key, value in list(meta.items()):
        if value is None:
            meta[key] = ""
        elif not isinstance(value, (str, int, float, bool)):
            meta[key] = str(value)
    return doc


def load_documents() -> list[Document]:
    """Every supported file under the knowledge directory, chunked and tagged."""
    root = settings.knowledge_dir
    if not root.exists():
        return []

    docs: list[Document] = []
    seen: set[str] = set()

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        source = path.relative_to(root).as_posix()
        for doc in _load_one(path, source):
            if not doc.page_content.strip():
                continue
            doc = _normalise(doc, source, path.suffix.lower())
            # Identical boilerplate in two places would collide on chunk_id and break the
            # id-keyed upsert, so the first occurrence wins.
            if doc.metadata["chunk_id"] in seen:
                continue
            seen.add(doc.metadata["chunk_id"])
            docs.append(doc)

    return docs
