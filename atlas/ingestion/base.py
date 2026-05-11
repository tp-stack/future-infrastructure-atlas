from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IngestionResult:
    dataset_key: str
    manifest: dict[str, Any] = field(default_factory=dict)
    records_raw: int = 0
    records_loaded: int = 0
    records_rejected: int = 0
    rejected_details: list[dict[str, Any]] = field(default_factory=list)
    processed_path: Path | None = None
    cache_path: Path | None = None


class IngestionPipeline:
    def __init__(self, dataset_key: str, file_path: str | Path) -> None:
        self.dataset_key = dataset_key
        self.file_path = Path(file_path)

    def run(self) -> IngestionResult:
        from atlas.ingestion.run import run_ingestion

        return run_ingestion(self.dataset_key, self.file_path)
