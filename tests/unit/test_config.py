"""Unit tests for config loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pfx2pem.config import CertEntry, Config, load_config


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _base_data(tmp_path: Path, **overrides) -> dict:
    data = {
        "importDir": str(tmp_path / "import"),
        "exportDir": str(tmp_path / "export"),
        "certificates": [
            {"cnpj": "72677008000106", "password": "senha123", "codes": ["000015"]}
        ],
    }
    data.update(overrides)
    return data


class TestLoadConfig:
    def test_basic(self, tmp_path):
        cfg = load_config(_write_config(tmp_path, _base_data(tmp_path)))

        assert cfg.import_dir == tmp_path / "import"
        assert cfg.export_dir == tmp_path / "export"
        assert len(cfg.certificates) == 1

    def test_cert_fields(self, tmp_path):
        cfg = load_config(_write_config(tmp_path, _base_data(tmp_path)))
        entry = cfg.certificates[0]

        assert entry.cnpj == "72677008000106"
        assert entry.password == "senha123"
        assert entry.codes == ["000015"]

    def test_multiple_codes(self, tmp_path):
        data = _base_data(tmp_path)
        data["certificates"][0]["codes"] = ["000015", "000013", "000007"]
        cfg = load_config(_write_config(tmp_path, data))

        assert cfg.certificates[0].codes == ["000015", "000013", "000007"]

    def test_codes_defaults_to_cnpj_when_absent(self, tmp_path):
        data = _base_data(tmp_path)
        del data["certificates"][0]["codes"]
        cfg = load_config(_write_config(tmp_path, data))

        assert cfg.certificates[0].codes == ["72677008000106"]

    def test_codes_defaults_to_cnpj_when_empty(self, tmp_path):
        data = _base_data(tmp_path)
        data["certificates"][0]["codes"] = []
        cfg = load_config(_write_config(tmp_path, data))

        assert cfg.certificates[0].codes == ["72677008000106"]

    def test_multiple_certificates(self, tmp_path):
        data = _base_data(tmp_path)
        data["certificates"].append(
            {"cnpj": "12345678000195", "password": "outra", "codes": ["000020"]}
        )
        cfg = load_config(_write_config(tmp_path, data))

        assert len(cfg.certificates) == 2

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nao_existe.json")

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{ invalido", encoding="utf-8")
        with pytest.raises(Exception):
            load_config(path)


class TestCertMap:
    def test_cert_map_by_cnpj(self, tmp_path):
        data = _base_data(tmp_path)
        data["certificates"].append(
            {"cnpj": "12345678000195", "password": "outra", "codes": ["000020"]}
        )
        cfg = load_config(_write_config(tmp_path, data))
        m = cfg.cert_map

        assert "72677008000106" in m
        assert "12345678000195" in m
        assert m["72677008000106"].codes == ["000015"]

    def test_cert_map_returns_entry(self, tmp_path):
        cfg = load_config(_write_config(tmp_path, _base_data(tmp_path)))
        entry = cfg.cert_map["72677008000106"]

        assert isinstance(entry, CertEntry)
        assert entry.password == "senha123"
