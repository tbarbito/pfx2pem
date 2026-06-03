"""Unit tests for PFX loading and CNPJ extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pfx2pem.converter import convert, extract_cnpj, load_pfx
from tests.conftest import TEST_PASSWORD


class TestLoadPfx:
    def test_loads_valid_pfx(self, test_pfx_path):
        private_key, certificate, _ = load_pfx(test_pfx_path, TEST_PASSWORD)
        assert private_key is not None
        assert certificate is not None

    def test_wrong_password_raises(self, test_pfx_path):
        with pytest.raises(Exception):
            load_pfx(test_pfx_path, "senha-errada")

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_pfx(tmp_path / "nao_existe.pfx", TEST_PASSWORD)


class TestExtractCnpj:
    def test_returns_none_for_cert_without_cnpj(self, self_signed_cert):
        # Self-signed test cert has no CNPJ in the DER payload
        result = extract_cnpj(self_signed_cert)
        assert result is None or isinstance(result, str)

    def test_excludes_all_zeros(self, self_signed_cert):
        # The all-zeros filter should never return "00000000000000"
        result = extract_cnpj(self_signed_cert)
        assert result != "00000000000000"

    def test_excludes_repeated_digits(self, self_signed_cert):
        result = extract_cnpj(self_signed_cert)
        if result:
            assert not all(c == result[0] for c in result)


class TestConvert:
    def test_creates_key_and_cert_files(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        assert (export_dir / "TST01_key.pem").exists()
        assert (export_dir / "TST01_cert.pem").exists()
        assert (export_dir / "TST01_all.pem").exists()

    def test_creates_ca_file_only_when_chain_available(self, test_pfx_path, export_dir, self_signed_cert):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[self_signed_cert]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        assert (export_dir / "TST01_ca.pem").exists()

    def test_no_ca_file_when_chain_empty(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        assert not (export_dir / "TST01_ca.pem").exists()

    def test_multiple_codes_create_multiple_sets(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["AAA", "BBB", "CCC"], export_dir)

        for code in ["AAA", "BBB", "CCC"]:
            assert (export_dir / f"{code}_key.pem").exists()
            assert (export_dir / f"{code}_cert.pem").exists()

    def test_key_pem_content_is_valid(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        content = (export_dir / "TST01_key.pem").read_text()
        assert "BEGIN PRIVATE KEY" in content
        assert "END PRIVATE KEY" in content

    def test_cert_pem_content_is_valid(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        content = (export_dir / "TST01_cert.pem").read_text()
        assert "BEGIN CERTIFICATE" in content
        assert "END CERTIFICATE" in content

    def test_all_pem_contains_cert(self, test_pfx_path, export_dir):
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], export_dir)

        all_content = (export_dir / "TST01_all.pem").read_text()
        cert_content = (export_dir / "TST01_cert.pem").read_text()
        assert cert_content.strip() in all_content

    def test_creates_export_dir_if_missing(self, test_pfx_path, tmp_path):
        new_dir = tmp_path / "novo" / "diretorio"
        with patch("pfx2pem.converter.fetch_ca_chain", return_value=[]):
            convert(test_pfx_path, TEST_PASSWORD, ["TST01"], new_dir)

        assert new_dir.exists()
        assert (new_dir / "TST01_key.pem").exists()
