"""Unit tests for CA chain resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.serialization import Encoding

from pfx2pem.chain import _get_aia_url, _parse_cert_bytes, fetch_ca_chain


class TestGetAiaUrl:
    def test_returns_none_for_self_signed(self, self_signed_cert):
        assert _get_aia_url(self_signed_cert) is None

    def test_returns_url_when_aia_present(self, self_signed_key):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
        import datetime

        attrs = [x509.NameAttribute(NameOID.COMMON_NAME, "Leaf")]
        issuer_attrs = [x509.NameAttribute(NameOID.COMMON_NAME, "Issuer")]

        aia = x509.AuthorityInformationAccess([
            x509.AccessDescription(
                AuthorityInformationAccessOID.CA_ISSUERS,
                x509.UniformResourceIdentifier("http://example.com/ca.p7c"),
            )
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name(attrs))
            .issuer_name(x509.Name(issuer_attrs))
            .public_key(self_signed_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            )
            .add_extension(aia, critical=False)
            .sign(self_signed_key, hashes.SHA256())
        )
        assert _get_aia_url(cert) == "http://example.com/ca.p7c"


class TestParseCertBytes:
    def test_parses_der_certificate(self, self_signed_cert):
        der = self_signed_cert.public_bytes(Encoding.DER)
        certs = _parse_cert_bytes(der)

        assert len(certs) == 1
        assert certs[0].subject == self_signed_cert.subject

    def test_returns_empty_for_garbage(self):
        assert _parse_cert_bytes(b"not a cert") == []


class TestFetchCaChain:
    def test_self_signed_returns_empty(self, self_signed_cert):
        chain = fetch_ca_chain(self_signed_cert)
        assert chain == []

    def test_network_error_raises_runtime_error(self, self_signed_key):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
        import datetime

        aia = x509.AuthorityInformationAccess([
            x509.AccessDescription(
                AuthorityInformationAccessOID.CA_ISSUERS,
                x509.UniformResourceIdentifier("http://unreachable.invalid/ca.p7c"),
            )
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Leaf")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Issuer")]))
            .public_key(self_signed_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            )
            .add_extension(aia, critical=False)
            .sign(self_signed_key, hashes.SHA256())
        )
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            with pytest.raises(RuntimeError, match="Falha ao baixar"):
                fetch_ca_chain(cert)

    def test_log_fn_called_with_url(self, self_signed_key):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
        import datetime

        url = "http://example.com/ca.p7c"
        aia = x509.AuthorityInformationAccess([
            x509.AccessDescription(
                AuthorityInformationAccessOID.CA_ISSUERS,
                x509.UniformResourceIdentifier(url),
            )
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Leaf")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Issuer")]))
            .public_key(self_signed_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            )
            .add_extension(aia, critical=False)
            .sign(self_signed_key, hashes.SHA256())
        )
        log_calls = []
        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            with pytest.raises(RuntimeError):
                fetch_ca_chain(cert, log_fn=log_calls.append)

        assert url in log_calls
