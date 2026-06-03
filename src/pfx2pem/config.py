from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CertEntry:
    cnpj: str
    password: str
    codes: list[str]


@dataclass
class Config:
    import_dir: Path
    export_dir: Path
    certificates: list[CertEntry]

    @property
    def cert_map(self) -> dict[str, CertEntry]:
        return {e.cnpj: e for e in self.certificates}


def load_config(path: Path) -> Config:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return Config(
        import_dir=Path(data["importDir"]),
        export_dir=Path(data["exportDir"]),
        certificates=[
            CertEntry(
                cnpj=entry["cnpj"],
                password=entry["password"],
                codes=entry.get("codes") or [entry["cnpj"]],
            )
            for entry in data["certificates"]
        ],
    )
