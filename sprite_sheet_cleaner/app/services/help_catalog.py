from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class HelpDocument:
    document_id: str
    title: str
    description: str
    filename: str


class HelpCatalog:
    """Load the indexed Markdown help bundled with the application."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = self._resolve_root(Path(root) if root is not None else None)
        self.documents = self._load_documents()

    @staticmethod
    def _resolve_root(explicit_root: Path | None) -> Path:
        if explicit_root is not None:
            return explicit_root.resolve()

        candidates: list[Path] = []
        frozen_root = getattr(sys, "_MEIPASS", None)
        if frozen_root:
            candidates.append(Path(frozen_root) / "help")
        module_root = Path(__file__).resolve()
        candidates.extend(
            (
                module_root.parents[3] / "help",
                module_root.parents[2] / "help",
                Path.cwd() / "help",
            )
        )
        for candidate in candidates:
            if (candidate / "index.json").is_file():
                return candidate
        return candidates[0]

    def _load_documents(self) -> tuple[HelpDocument, ...]:
        index_path = self.root / "index.json"
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Help index not found: {index_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Help index is not valid JSON: {index_path}") from exc

        if not isinstance(data, dict) or int(data.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported help index schema.")
        raw_documents = data.get("documents")
        if not isinstance(raw_documents, list):
            raise ValueError("Help index must contain a documents list.")

        documents: list[HelpDocument] = []
        seen_ids: set[str] = set()
        for raw_document in raw_documents:
            if not isinstance(raw_document, dict):
                raise ValueError("Each help document entry must be an object.")
            document_id = str(raw_document.get("id") or "").strip()
            title = str(raw_document.get("title") or "").strip()
            description = str(raw_document.get("description") or "").strip()
            filename = str(raw_document.get("path") or "").strip()
            if not document_id or not title or not filename:
                raise ValueError("Each help document needs an id, title, and path.")
            if document_id in seen_ids:
                raise ValueError(f"Duplicate help document id: {document_id}")
            relative_path = Path(filename)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(f"Help document path escapes the help folder: {filename}")
            if relative_path.suffix.lower() != ".md":
                raise ValueError(f"Help document must be Markdown: {filename}")
            if not (self.root / relative_path).is_file():
                raise FileNotFoundError(f"Help document not found: {self.root / relative_path}")
            seen_ids.add(document_id)
            documents.append(HelpDocument(document_id, title, description, filename))
        return tuple(documents)

    def read(self, document: HelpDocument | str) -> str:
        if isinstance(document, str):
            document_id = document
            document = next((item for item in self.documents if item.document_id == document_id), None)
            if document is None:
                raise KeyError(f"Unknown help document: {document_id}")
        return (self.root / document.filename).read_text(encoding="utf-8")
