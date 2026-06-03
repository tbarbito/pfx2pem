from __future__ import annotations

import urllib.request
import warnings
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID


def _get_aia_url(cert: x509.Certificate) -> str | None:
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        for access in aia.value:
            if access.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                return access.access_location.value
    except x509.ExtensionNotFound:
        pass
    return None


def _parse_cert_bytes(data: bytes) -> list[x509.Certificate]:
    try:
        return [x509.load_der_x509_certificate(data)]
    except Exception:
        pass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return list(pkcs7.load_der_pkcs7_certificates(data))
    except Exception:
        pass
    return []


def fetch_ca_chain(
    leaf_cert: x509.Certificate,
    log_fn: object = None,
) -> list[x509.Certificate]:
    chain: list[x509.Certificate] = []
    current = leaf_cert

    for _ in range(10):
        if current.issuer == current.subject:
            break

        url = _get_aia_url(current)
        if not url:
            break

        if log_fn:
            log_fn(url)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pfx2pem/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except Exception as exc:
            raise RuntimeError(f"Falha ao baixar CA cert em {url}: {exc}") from exc

        certs = _parse_cert_bytes(data)
        if not certs:
            raise RuntimeError(f"Nao foi possivel interpretar o cert em {url}")

        chain.extend(certs)
        current = certs[0]

    return chain
