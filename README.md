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
pfx2pem batch ./import-dir --config config.json
```

Se `import-dir` for omitido, usa o `importDir` do config:

```bash
pfx2pem batch --config config.json
```

## Configuracao (batch)

Copie `config.example.json` para `config.json` e preencha:

```json
{
  "importDir": "C:\\certs\\import",
  "exportDir": "C:\\certs\\export",
  "certificates": [
    {
      "cnpj": "72677008000106",
      "password": "senha-do-pfx",
      "codes": ["000015", "000013", "000007"]
    }
  ]
}
```

> **Importante:** o `config.json` esta no `.gitignore`. Nunca faca commit -- ele contem senhas.

## Como o CNPJ e identificado

A ferramenta localiza o CNPJ na seguinte ordem:

1. **Nome do arquivo**: se o PFX se chamar `72677008000106.pfx`
2. **Conteudo do certificado**: extrai o CNPJ embutido nos bytes DER do certificado (padrao ICP-Brasil)

Se o CNPJ nao estiver no `config.json`, ele mesmo e usado como prefixo dos arquivos de saida.

## Multiplos codigos por CNPJ

Um CNPJ pode mapear para varios codigos de entidade. O certificado e processado uma vez e os arquivos sao gravados para cada codigo:

```json
{
  "cnpj": "72677008000106",
  "password": "sua-senha",
  "codes": ["000015", "000013", "000007"]
}
```

## Cadeia CA

A cadeia CA e construida automaticamente seguindo as URLs AIA (Authority Information Access) embutidas no certificado, subindo ate a raiz autoassinada. Funciona nativamente com certificados ICP-Brasil.

## Licenca

MIT
