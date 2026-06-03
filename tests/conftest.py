"""Shared fixtures for unit and E2E tests."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

TEST_PASSWORD = "test-password-123"
TEST_CNPJ = "72677008000106"

# ---------------------------------------------------------------------------
# Real-cert markers (E2E only — skipped in CI unless env vars are set)
# ---------------------------------------------------------------------------

REAL_PFX = os.environ.get("PFX2PEM_TEST_PFX")
REAL_PASSWORD = os.environ.get("PFX2PEM_TEST_PASSWORD")

requires_real_cert = pytest.mark.skipif(
    not REAL_PFX or not REAL_PASSWORD,
    reason="Set PFX2PEM_TEST_PFX and PFX2PEM_TEST_PASSWORD to run real-cert tests",
)

# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------


def _make_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_cert(
    key: rsa.RSAPrivateKey,
    subject_attrs: list[x509.NameAttribute],
    issuer_key: rsa.RSAPrivateKey | None = None,
    issuer_attrs: list[x509.NameAttribute] | None = None,
    extensions: list[tuple] | None = None,
) -> x509.Certificate:
    issuer_key = issuer_key or key
    issuer_name = x509.Name(issuer_attrs or subject_attrs)
    subject_name = x509.Name(subject_attrs)

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject_name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
    )
    for ext, critical in (extensions or []):
        builder = builder.add_extension(ext, critical=critical)

    return builder.sign(issuer_key, hashes.SHA256())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def self_signed_key() -> rsa.RSAPrivateKey:
    return _make_key()


@pytest.fixture(scope="session")
def self_signed_cert(self_signed_key) -> x509.Certificate:
    attrs = [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "59975201000157"),
        x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE LTDA"),
    ]
    return _make_cert(self_signed_key, attrs)


@pytest.fixture(scope="session")
def test_pfx_path(tmp_path_factory, self_signed_key, self_signed_cert) -> Path:
    pfx_data = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=self_signed_key,
        cert=self_signed_cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(TEST_PASSWORD.encode()),
    )
    path = tmp_path_factory.mktemp("pfx") / f"{TEST_CNPJ}.pfx"
    path.write_bytes(pfx_data)
    return path


@pytest.fixture
def export_dir(tmp_path) -> Path:
    d = tmp_path / "export"
    d.mkdir()
    return d


@pytest.fixture
def import_dir(tmp_path, test_pfx_path) -> Path:
    d = tmp_path / "import"
    d.mkdir()
    import shutil
    shutil.copy(test_pfx_path, d / test_pfx_path.name)
    return d


@pytest.fixture
def config_file(tmp_path, import_dir, export_dir) -> Path:
    data = {
        "importDir": str(import_dir),
        "exportDir": str(export_dir),
        "certificates": [
            {
                "cnpj": TEST_CNPJ,
                "password": TEST_PASSWORD,
                "codes": ["000015", "000013"],
            }
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
