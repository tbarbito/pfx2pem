# pfx2pem

Ferramenta PowerShell para converter certificados PFX para o formato PEM, com suporte a multiplos codigos de entidade por CNPJ e resolucao automatica da cadeia CA via URLs AIA.

## Arquivos gerados

Para cada codigo de entidade configurado, a ferramenta gera:

| Arquivo | Conteudo |
|---|---|
| `{codigo}_key.pem` | Chave privada |
| `{codigo}_cert.pem` | Certificado do cliente |
| `{codigo}_ca.pem` | Cadeia CA (intermediarios + raiz) |
| `{codigo}_all.pem` | Certificado do cliente + cadeia CA combinados |

## Requisitos

- Windows com PowerShell 5.1+
- [OpenSSL](https://slproweb.com/products/Win32OpenSSL.html) instalado e disponivel no PATH (ou em um dos caminhos padrao de instalacao). O Git para Windows ja inclui o OpenSSL.
- Acesso a internet para baixar a cadeia CA no primeiro uso (via URLs AIA embutidas no certificado)

## Configuracao

1. Clone o repositorio
2. Copie `config.example.json` para `config.json`
3. Edite o `config.json` com seus valores:

```json
{
  "importDir": "C:\\certs\\import",
  "exportDir": "C:\\certs\\export",
  "certificates": [
    {
      "cnpj": "72677008000106",
      "password": "senha-do-pfx",
      "codes": ["000015", "000013"]
    }
  ]
}
```

> **Importante:** o `config.json` esta listado no `.gitignore`. Nunca faca commit dele -- ele contem senhas.

## Uso

Coloque os arquivos `.pfx` na pasta `importDir` configurada no `config.json` e execute:

```powershell
powershell -ExecutionPolicy Bypass -File pfx2pem.ps1
```

## Como o CNPJ e identificado

A ferramenta identifica o CNPJ do certificado na seguinte ordem:

1. **Nome do arquivo**: se o nome do PFX for um numero de 14 digitos (ex: `72677008000106.pfx`)
2. **Conteudo do certificado**: extrai o CNPJ embutido no conteudo DER do certificado (padrao nos certificados ICP-Brasil)

Se o CNPJ nao for encontrado no `config.json`, o proprio CNPJ e usado como prefixo dos arquivos de saida.

## Multiplos codigos por CNPJ

Um mesmo CNPJ pode ser mapeado para varios codigos de entidade. O certificado e processado uma unica vez e os arquivos de saida sao gravados para cada codigo:

```json
{
  "cnpj": "72677008000106",
  "password": "sua-senha",
  "codes": ["000015", "000013", "000007"]
}
```

Isso gera `000015_key.pem`, `000013_key.pem`, `000007_key.pem`, etc. -- todos com conteudo identico.

## Cadeia CA

A cadeia CA e construida automaticamente seguindo as URLs AIA (Authority Information Access) embutidas no certificado, subindo ate encontrar um certificado raiz autoassinado. Funciona nativamente com certificados ICP-Brasil.

## Licenca

MIT
