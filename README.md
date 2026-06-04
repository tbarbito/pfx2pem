# pfx2pem

CLI Python para converter certificados PFX para o formato PEM, voltada para uso com o
**TSS (Totvs Sped Service / Transmissao de Documentos Eletronicos)** do Protheus.

Nao requer OpenSSL instalado -- usa a biblioteca `cryptography` nativamente.

> **Aviso:** este projeto nao e uma ferramenta oficial nem homologada pela TOTVS S.A.
> Foi idealizado de forma pessoal como um facilitador para o processo de renovacao de certificados
> digitais no TSS. Use por sua conta e risco.

---

## Contexto de uso

O TSS armazena os certificados digitais das entidades fiscais na pasta `cert/` do seu diretorio
de instalacao, no formato PEM. Quando um certificado e renovado junto a certificadora, ele chega
no formato `.pfx` (PKCS#12) e precisa ser convertido antes de ser implantado no TSS.

**Fluxo completo de renovacao:**

```
1. Receber o .pfx da certificadora
2. Consultar o codigo da entidade no banco (tabela SPED001 -- ver abaixo)
3. Preencher o config.json com CNPJ, senha e codigo(s) da entidade
4. Executar: pfx2pem batch --config config.json
5. Parar o servico do TSS
6. Copiar os .pem gerados para a pasta cert/ do TSS
7. Subir o servico do TSS
```

---

## Obtendo o codigo da entidade (tabela SPED001)

O campo `codes` do config.json corresponde ao `ID_ENT` da tabela `SPED001` no banco do Protheus.
Use a query abaixo para localizar os codigos a partir dos CNPJs dos certificados que serao renovados.

### Oracle

```sql
SELECT DISTINCT
    cnpj,
    id_ent || ' - ' || cnpj AS ent_cnpj
FROM sped001
WHERE cnpj IN (
    'CNPJ_01',
    'CNPJ_02',
    'CNPJ_03'
)
AND d_e_l_e_t_ = ' '
ORDER BY cnpj;
```

### SQL Server

```sql
SELECT DISTINCT
    cnpj,
    id_ent + ' - ' + cnpj AS ent_cnpj
FROM sped001
WHERE cnpj IN (
    'CNPJ_01',
    'CNPJ_02',
    'CNPJ_03'
)
AND d_e_l_e_t_ = ' '
ORDER BY cnpj;
```

### PostgreSQL

```sql
SELECT DISTINCT
    cnpj,
    id_ent || ' - ' || cnpj AS ent_cnpj
FROM sped001
WHERE cnpj IN (
    'CNPJ_01',
    'CNPJ_02',
    'CNPJ_03'
)
AND d_e_l_e_t_ = ' '
ORDER BY cnpj;
```

O resultado traz pares `ID_ENT - CNPJ`. Use o `ID_ENT` como valor do campo `codes` no `config.json`.

---

## Arquivos gerados

Para cada codigo de entidade configurado:

| Arquivo | Conteudo |
|---|---|
| `{codigo}_key.pem` | Chave privada |
| `{codigo}_cert.pem` | Certificado do cliente |
| `{codigo}_ca.pem` | Cadeia CA (intermediarios + raiz) |
| `{codigo}_all.pem` | Certificado + cadeia CA combinados |

---

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

---

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
  "exportDir": "C:\\tss\\cert",
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
| `exportDir` | string | **obrigatorio** | Diretorio de saida dos `.pem`. Para uso direto com o TSS, aponte para a pasta `cert/` da instalacao |
| `certificates` | array | **obrigatorio** | Lista de certificados. Cada item define um CNPJ, sua senha e os codigos de entidade |
| `certificates[].cnpj` | string | **obrigatorio** | CNPJ do certificado (14 digitos, sem pontuacao) |
| `certificates[].password` | string | **obrigatorio** | Senha do arquivo `.pfx` fornecida pela certificadora |
| `certificates[].codes` | array | `[cnpj]` | Codigos de entidade (`ID_ENT` da tabela `SPED001`) usados como prefixo dos arquivos de saida. Se omitido, usa o proprio CNPJ |

### Multiplos codigos por CNPJ

Um mesmo CNPJ pode estar associado a varios codigos de entidade no Protheus. O certificado e
processado uma unica vez e os arquivos PEM sao gravados para cada codigo, todos com conteudo identico:

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
