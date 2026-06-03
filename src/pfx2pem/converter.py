from __future__ import annotations

import re
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

from .chain import fetch_ca_chain


def load_pfx(pfx_path: Path, password: str) -> tuple[object, x509.Certificate, list]:
    with open(pfx_path, "rb") as f:
        data = f.read()
    return load_key_and_certificates(data, password.encode())


def extract_cnpj(cert: x509.Certificate) -> str | None:
    der = cert.public_bytes(Encoding.DER)

    # Get CA CNPJ from subject OU to exclude (belongs to the certification authority)
    ca_cnpj: str | None = None
    for attr in cert.subject:
        if re.match(r"^\d{14}$", attr.value):
            ca_cnpj = attr.value
            break

    pattern = re.compile(rb"(?<![0-9])[0-9]{14}(?![0-9])")
    for match in pattern.finditer(der):
        val = match.group().decode()
        if re.match(r"^0{14}$", val):
            continue
        if re.match(r"^(.)\1{13}$", val):
            continue
        if val == ca_cnpj:
            continue
        return val

    return None


def convert(
    pfx_path: Path,
    password: str,
    codes: list[str],
    export_dir: Path,
    log_fn: object = None,
) -> str | None:
    private_key, certificate, _ = load_pfx(pfx_path, password)

    cnpj = extract_cnpj(certificate)

    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    cert_pem = certificate.public_bytes(Encoding.PEM)

    ca_chain = fetch_ca_chain(certificate, log_fn=log_fn)
    ca_pem = b"".join(c.public_bytes(Encoding.PEM) for c in ca_chain)
    all_pem = cert_pem + ca_pem if ca_pem else cert_pem

    export_dir.mkdir(parents=True, exist_ok=True)

    for code in codes:
        (export_dir / f"{code}_key.pem").write_bytes(key_pem)
        (export_dir / f"{code}_cert.pem").write_bytes(cert_pem)
        (export_dir / f"{code}_all.pem").write_bytes(all_pem)
        if ca_pem:
            (export_dir / f"{code}_ca.pem").write_bytes(ca_pem)

    return cnpj
