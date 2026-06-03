"""E2E tests for the pfx2pem CLI.

Synthetic tests run always (using a self-signed test PFX).
Real-cert tests require environment variables:
  PFX2PEM_TEST_PFX      - path to a real ICP-Brasil .pfx file
  PFX2PEM_TEST_PASSWORD - password for that file
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pfx2pem.cli import app
from tests.conftest import REAL_PASSWORD, REAL_PFX, TEST_PASSWORD, requires_real_cert

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pem_files_exist(directory: Path, code: str, with_ca: bool = True) -> None:
    assert (directory / f"{code}_key.pem").exists()
    assert (directory / f"{code}_cert.pem").exists()
    assert (directory / f"{code}_all.pem").exists()
    if with_ca:
        assert (directory / f"{code}_ca.pem").exists()


# ---------------------------------------------------------------------------
# convert command — synthetic (no network)
# ---------------------------------------------------------------------------


class TestConvertCommand:
    def test_basic_convert(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            result = runner.invoke(app, [
                "convert", str(test_pfx_path),
                "--password", TEST_PASSWORD,
                "--output", str(export_dir),
                "--code", "TST01",
            ])

        assert result.exit_code == 0
        _pem_files_exist(export_dir, "TST01", with_ca=False)

    def test_multiple_codes(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            result = runner.invoke(app, [
                "convert", str(test_pfx_path),
                "--password", TEST_PASSWORD,
                "--output", str(export_dir),
                "--code", "AAA",
                "--code", "BBB",
            ])

        assert result.exit_code == 0
        _pem_files_exist(export_dir, "AAA", with_ca=False)
        _pem_files_exist(export_dir, "BBB", with_ca=False)

    def test_missing_file_exits_1(self, export_dir):
        result = runner.invoke(app, [
            "convert", "nao_existe.pfx",
            "--password", "qualquer",
            "--output", str(export_dir),
        ])
        assert result.exit_code == 1

    def test_wrong_password_exits_1(self, test_pfx_path, export_dir):
        result = runner.invoke(app, [
            "convert", str(test_pfx_path),
            "--password", "senha-errada",
            "--output", str(export_dir),
        ])
        assert result.exit_code == 1

    def test_output_contains_cnpj_info(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            result = runner.invoke(app, [
                "convert", str(test_pfx_path),
                "--password", TEST_PASSWORD,
                "--output", str(export_dir),
            ])
        assert result.exit_code == 0
        assert "Concluido" in result.output

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output


# ---------------------------------------------------------------------------
# batch command — synthetic (no network)
# ---------------------------------------------------------------------------


class TestBatchCommand:
    def test_basic_batch(self, config_file, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            result = runner.invoke(app, ["batch", "--config", str(config_file)])

        assert result.exit_code == 0
        for code in ["000015", "000013"]:
            _pem_files_exist(export_dir, code, with_ca=False)

    def test_missing_config_exits_1(self, tmp_path):
        result = runner.invoke(app, ["batch", "--config", str(tmp_path / "nao_existe.json")])
        assert result.exit_code == 1

    def test_empty_import_dir_exits_0(self, tmp_path):
        import json
        empty_import = tmp_path / "empty"
        empty_import.mkdir()
        cfg = {
            "importDir": str(empty_import),
            "exportDir": str(tmp_path / "out"),
            "certificates": [],
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(cfg), encoding="utf-8")

        result = runner.invoke(app, ["batch", "--config", str(config_file)])
        assert result.exit_code == 0

    def test_output_shows_success(self, config_file):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            result = runner.invoke(app, ["batch", "--config", str(config_file)])

        assert "Sucesso: 1" in result.output
        assert "Falha: 0" in result.output


# ---------------------------------------------------------------------------
# Real-cert E2E (skipped unless env vars are set)
# ---------------------------------------------------------------------------


@requires_real_cert
class TestRealCert:
    def test_convert_generates_all_files(self, tmp_path):
        result = runner.invoke(app, [
            "convert", REAL_PFX,
            "--password", REAL_PASSWORD,
            "--output", str(tmp_path),
            "--code", "REAL01",
        ])
        assert result.exit_code == 0
        _pem_files_exist(tmp_path, "REAL01", with_ca=True)

    def test_key_pem_is_valid(self, tmp_path):
        runner.invoke(app, [
            "convert", REAL_PFX,
            "--password", REAL_PASSWORD,
            "--output", str(tmp_path),
            "--code", "REAL01",
        ])
        content = (tmp_path / "REAL01_key.pem").read_text()
        assert "BEGIN PRIVATE KEY" in content

    def test_ca_chain_has_multiple_certs(self, tmp_path):
        runner.invoke(app, [
            "convert", REAL_PFX,
            "--password", REAL_PASSWORD,
            "--output", str(tmp_path),
            "--code", "REAL01",
        ])
        content = (tmp_path / "REAL01_ca.pem").read_text()
        assert content.count("BEGIN CERTIFICATE") >= 2

    def test_all_pem_contains_cert_and_ca(self, tmp_path):
        runner.invoke(app, [
            "convert", REAL_PFX,
            "--password", REAL_PASSWORD,
            "--output", str(tmp_path),
            "--code", "REAL01",
        ])
        all_content = (tmp_path / "REAL01_all.pem").read_text()
        cert_content = (tmp_path / "REAL01_cert.pem").read_text().strip()
        ca_content = (tmp_path / "REAL01_ca.pem").read_text().strip()

        assert cert_content in all_content
        assert ca_content in all_content
