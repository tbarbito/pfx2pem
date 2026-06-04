# pfx2pem

CLI Python para converter certificados PFX para o formato PEM, com suporte a multiplos codigos de entidade por CNPJ e resolucao automatica da cadeia CA via URLs AIA.

Nao requer OpenSSL instalado -- usa a biblioteca `cryptography` nativamente.

## Arquivos gerados

Para cada codigo de entidade configurado:

| Arquivo | Conteudo |
|---|---|
| `{codigo}_key.pem` | Chave privada |
| `{codigo}_cert.pem` | Certificado do cliente |
| `{codigo}_ca.pem` | Cadeia CA (intermediarios + raiz) |
| `{codigo}_all.pem` | Certificado + cadeia CA combinados |

## Requisitos

- Python 3.11+
- Acesso a internet para baixar a cadeia CA no primeiro uso (via URLs AIA embutidas no certificado)

## Instalacao

```bash
pip install git+https://github.com/tbarbito/pfx2pem.git
```

Ou com `uv`:

```bash
uv tool install git+https://github.com/tbarbito/pfx2pem.git
```

## Uso

### Converter um unico arquivo

```bash
pfx2pem convert certificado.pfx --password minha-senha
```

Com diretorio de saida e codigos de entidade personalizados:

```bash
pfx2pem convert certificado.pfx --password minha-senha --output ./pems --code 000015 --code 000013
```

### Conversao em lote via config.json

```bash
pfx2pem batch --config config.json
```

Sobrepondo o diretorio de importacao:

```bash
pfx2pem batch ./import-dir --config config.json
```

---

## Configuracao (batch)

Copie `config.example.json` para `config.json` e preencha com os valores do seu ambiente:

```bash
copy config.example.json config.json
```

> **Importante:** o `config.json` esta no `.gitignore`. Nunca faca commit -- ele contem senhas de certificados.

### Referencia completa do config.json

```json
{
  "importDir": "C:\\certs\\import",
  "exportDir": "C:\\certs\\export",
  "certificates": [
    {
      "cnpj": "72677008000106",
      "password": "senha-do-pfx",
      "codes": ["000015", "000013", "000007"]
    },
    {
      "cnpj": "12345678000195",
      "password": "outra-senha",
      "codes": ["000020"]
    }
  ]
}
```

| Campo | Tipo | Padrao | Descricao |
|---|---|---|---|
| `importDir` | string | **obrigatorio** | Diretorio onde estao os arquivos `.pfx` a converter |
| `exportDir` | string | **obrigatorio** | Diretorio onde os arquivos `.pem` serao gravados (criado automaticamente se nao existir) |
| `certificates` | array | **obrigatorio** | Lista de certificados mapeados. Cada item define um CNPJ, sua senha e os codigos de entidade de saida |
| `certificates[].cnpj` | string | **obrigatorio** | CNPJ do certificado (14 digitos, sem pontuacao) |
| `certificates[].password` | string | **obrigatorio** | Senha do arquivo `.pfx` fornecida pela certificadora |
| `certificates[].codes` | array | `[cnpj]` | Codigos de entidade usados como prefixo dos arquivos de saida. Se omitido, usa o proprio CNPJ |

### Multiplos codigos por CNPJ

Um mesmo CNPJ pode mapear para varios codigos de entidade. O certificado e processado uma unica vez
e os arquivos PEM sao gravados para cada codigo, todos com conteudo identico:

```json
{
  "cnpj": "72677008000106",
  "password": "sua-senha",
  "codes": ["000015", "000013", "000007"]
}
```

Isso gera `000015_key.pem`, `000013_key.pem`, `000007_key.pem`, etc.

---

## Como o CNPJ e identificado

A ferramenta localiza o CNPJ do certificado na seguinte ordem:

1. **Nome do arquivo**: se o PFX se chamar `72677008000106.pfx`
2. **Conteudo do certificado**: extrai o CNPJ embutido nos bytes DER (padrao ICP-Brasil)

Se o CNPJ nao estiver mapeado no `config.json`, ele mesmo e usado como prefixo dos arquivos de saida.

---

## Cadeia CA

A cadeia CA e construida automaticamente seguindo as URLs AIA (Authority Information Access)
embutidas no certificado, subindo ate a raiz autoassinada. Funciona nativamente com certificados ICP-Brasil.

A conexao com a internet e necessaria apenas no primeiro uso ou quando o certificado for renovado.

---

## Licenca

MIT
