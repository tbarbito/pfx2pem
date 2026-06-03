# pfx2pem

PowerShell script that converts PFX certificates to PEM format files, with support for multiple entity codes per CNPJ and automatic CA chain resolution via AIA URLs.

## Output files

For each configured entity code, the script generates:

| File | Contents |
|---|---|
| `{code}_key.pem` | Private key |
| `{code}_cert.pem` | Client certificate |
| `{code}_ca.pem` | CA chain (intermediates + root) |
| `{code}_all.pem` | Client certificate + CA chain combined |

## Requirements

- Windows with PowerShell 5.1+
- [OpenSSL](https://slproweb.com/products/Win32OpenSSL.html) installed and available in PATH (or one of the default installation paths)
- Internet access to download the CA chain on first use (via AIA URLs embedded in the certificate)

## Setup

1. Clone the repository
2. Copy `config.example.json` to `config.json`
3. Edit `config.json` with your values:

```json
{
  "importDir": "C:\\certs\\import",
  "exportDir": "C:\\certs\\export",
  "certificates": [
    {
      "cnpj": "72677008000106",
      "password": "your-pfx-password",
      "codes": ["000015", "000013"]
    }
  ]
}
```

> **Important:** `config.json` is listed in `.gitignore`. Never commit it — it contains passwords.

## Usage

Place your `.pfx` files in the `importDir` configured in `config.json`, then run:

```powershell
powershell -ExecutionPolicy Bypass -File pfx2pem.ps1
```

## How CNPJ is resolved

The script identifies the certificate CNPJ in the following order:

1. **Filename**: if the PFX filename is a 14-digit number (e.g. `72677008000106.pfx`)
2. **Certificate bytes**: extracts the CNPJ embedded in the certificate's DER content (standard for ICP-Brasil certificates)

If the CNPJ is not found in `config.json`, the CNPJ itself is used as the output file prefix.

## Multiple codes per CNPJ

One CNPJ can be mapped to multiple entity codes. The certificate is processed once and the output files are written for each code:

```json
{
  "cnpj": "72677008000106",
  "password": "your-password",
  "codes": ["000015", "000013", "000007"]
}
```

This generates `000015_key.pem`, `000013_key.pem`, `000007_key.pem`, etc. — all with identical content.

## CA chain

The CA chain is built automatically by following the AIA (Authority Information Access) URLs embedded in the certificate, walking up the chain until a self-signed root is reached. This works out of the box with ICP-Brasil certificates.

## License

MIT
