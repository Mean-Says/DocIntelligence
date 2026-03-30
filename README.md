# DocIntelligence

Plataforma de extração e inteligência sobre documentos. Recebe PDFs e imagens, retorna JSON estruturado com score de confiança por campo.

Diferencial: **aprende com o uso** — cada documento processado por IA gera uma regra regex que, quando validada, resolve os próximos documentos similares localmente (sem custo de API).

---

## Como funciona

### Pipeline de extração (4 níveis)

Cada nível só ativa se o anterior ficou abaixo do threshold de confiança:

```
Nível 1 — pdfplumber (PDF binário)     threshold ≥ 0.85  grátis, < 100ms
Nível 2 — regras regex do banco        threshold ≥ 0.82  grátis, < 50ms
Nível 3 — Groq / Llama 3.3 70B        threshold ≥ 0.78  ~$0.0002/doc
Nível 4 — Claude Sonnet                sempre aceita      ~$0.003/doc
```

### Loop de aprendizado

Quando o Nível 3 ou 4 processa um documento:

```
AI extrai campo
    → Claude gera regex candidata
    → Groq valida a regex no mesmo texto
    → confiança ≥ 0.90: regra salva e ativa imediatamente
    → confiança 0.70–0.90: acumula 3 documentos antes de promover
    → confiança < 0.70: fila de revisão humana
```

Após 3 meses, a meta é resolver 70%+ dos documentos no Nível 1 ou 2.

### Isolamento de regras

- **Global** (`scope=global`): padrões padronizados (NF-e federal, email, CPF/CNPJ) — compartilhados entre todos os clientes
- **Cliente** (`scope=client`): layouts específicos de uma empresa — isolados, nunca vazam entre clientes

---

## Tipos de documento suportados

| Tipo | `doc_type` | Campos extraídos |
|---|---|---|
| Nota Fiscal Eletrônica | `nfe` | cnpj_emitente, cnpj_destinatario, valor_total, data_emissao, numero_nf |
| Conta de Energia | `conta_luz` | valor_total, vencimento, consumo_kwh, distribuidora |
| Currículo | `curriculo` | nome, email, telefone, linkedin |
| Contrato | `contrato` | partes, valor, prazo |

---

## Setup

### Pré-requisitos

- Docker e Docker Compose
- Python 3.12+
- Chaves de API: Anthropic e Groq

### Inicialização

```bash
# 1. Copiar e preencher variáveis de ambiente
cp .env.example .env
# editar .env: ANTHROPIC_API_KEY, GROQ_API_KEY, e configs do R2

# 2. Subir serviços
docker-compose up -d db redis

# 3. Rodar migrations
alembic upgrade head

# 4. Carregar regras iniciais
python seed/load_rules.py

# 5. Subir API e worker
docker-compose up api worker
```

Ou use o slash command `/init` no Claude Code para fazer tudo automaticamente.

### Desenvolvimento local (sem Docker)

```bash
# Instalar dependências
pip install -e ".[dev]"

# Dependências de sistema (macOS)
brew install tesseract tesseract-lang

# Subir apenas DB e Redis via Docker
docker-compose up -d db redis

# Rodar API
uvicorn app.main:app --reload

# Rodar worker (terminal separado)
python -m arq app.workers.arq_settings.WorkerSettings
```

---

## API

### Autenticação

Todas as rotas exigem `Authorization: Bearer <api_key>`.

### Endpoints

#### `POST /v1/extract`

Envia documento para extração. Retorna `202 Accepted` com `job_id` para polling.

**Request** (`multipart/form-data`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `file` | binary | sim | PDF, JPG, PNG, TIFF ou WEBP |
| `doc_type` | string | não | Hint do tipo: `nfe`, `curriculo`, `conta_luz`, `contrato` |

**Response `202`:**

```json
{
  "job_id": "arq:job:550e8400-e29b-41d4-a716",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/v1/extract/jobs/arq:job:550e8400-e29b-41d4-a716"
}
```

---

#### `GET /v1/extract/jobs/{job_id}`

Polling do resultado. Retorna `status: done` quando pronto.

**Response quando pronto:**

```json
{
  "job_id": "arq:job:...",
  "status": "done",
  "document_id": "550e8400-...",
  "doc_type": "nfe",
  "doc_type_confidence": 0.95,
  "processing_level": 2,
  "data": {
    "cnpj_emitente": "12345678000199",
    "valor_total": "1250.00",
    "data_emissao": "2026-03-15",
    "numero_nf": "000123456"
  },
  "confidence": {
    "cnpj_emitente": 0.92,
    "valor_total": 0.90,
    "data_emissao": 0.91,
    "numero_nf": 0.93
  },
  "overall_confidence": 0.915,
  "processing_ms": 87
}
```

`processing_level: 2` significa que foi resolvido por regras locais (sem custo de API).

**Status possíveis:** `pending` → `processing` → `done` | `failed`

---

#### `POST /v1/feedback`

Corrige um campo extraído incorretamente. Se o documento foi processado por AI, dispara um novo ciclo de aprendizado.

**Request:**

```json
{
  "document_id": "550e8400-...",
  "field": "valor_total",
  "correct_value": "1500.00"
}
```

**Response:**

```json
{
  "accepted": true,
  "triggered_relearn": true
}
```

`triggered_relearn: true` indica que o sistema vai tentar gerar uma regra melhor com o valor correto como ground truth.

---

#### `GET /health`

```json
{ "status": "ok", "env": "development" }
```

---

## Estrutura do projeto

```
docintelligence/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Settings (pydantic-settings) — fonte única de verdade
│   ├── db.py                      # Engine async + SessionLocal
│   ├── deps.py                    # Injeção de dependências (session, auth)
│   │
│   ├── api/v1/
│   │   ├── extract.py             # POST /v1/extract, GET /v1/extract/jobs/{id}
│   │   ├── feedback.py            # POST /v1/feedback
│   │   └── router.py              # Agrega rotas v1
│   │
│   ├── models/                    # SQLModel — ORM + schema em um lugar só
│   │   ├── client.py              # Clientes da API
│   │   ├── document.py            # Documentos enviados
│   │   ├── extraction.py          # Resultado da extração (fields + confidence)
│   │   ├── rule.py                # Regras ativas + candidatas
│   │   └── feedback.py            # Correções humanas
│   │
│   ├── pipeline/
│   │   ├── orchestrator.py        # ← arquivo mais crítico: decide qual nível ativar
│   │   ├── detector.py            # Detecta tipo de arquivo e tipo de documento
│   │   └── levels/
│   │       ├── level1_binary.py   # pdfplumber + padrões universais
│   │       ├── level3_slm.py      # Groq / Llama 3.3 70B
│   │       └── level4_claude.py   # Anthropic Claude Sonnet
│   │
│   ├── rule_engine/
│   │   ├── loader.py              # Carrega regras do DB → cache Redis (TTL 5min)
│   │   └── matcher.py             # ← hot path: aplica regex no texto
│   │
│   ├── storage/
│   │   └── r2.py                  # Upload/download Cloudflare R2 (S3-compatible)
│   │
│   ├── utils/
│   │   ├── confidence.py          # Cálculo de confiança ponderada por campo
│   │   ├── normalizers.py         # strip, digits_only, date_iso, currency_brl
│   │   └── ocr.py                 # Tesseract via pymupdf
│   │
│   └── workers/
│       ├── tasks.py               # process_document + run_learning_loop (ARQ)
│       └── arq_settings.py        # Configuração do worker ARQ
│
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py # Migration inicial com todas as tabelas
│
├── seed/
│   ├── rules.json                 # Regras handcrafted iniciais (NF-e, currículo, conta de luz)
│   └── load_rules.py              # Script para carregar seed no banco
│
├── tests/
│   ├── unit/                      # Testes de matcher, confidence, normalizers
│   └── integration/               # Testes do pipeline completo
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Banco de dados

### Tabelas principais

| Tabela | Propósito |
|---|---|
| `clients` | Clientes da API com api_key_hash (bcrypt) |
| `documents` | Cada arquivo enviado: status, tipo, nível de processamento |
| `extractions` | Resultado JSON + confidence_scores (JSONB) por documento |
| `rules` | Regras regex ativas — global ou por cliente |
| `rule_candidates` | Regras geradas por AI aguardando validação ou acúmulo |
| `feedbacks` | Correções humanas que realimentam o aprendizado |

### Regras: global vs cliente

```sql
-- Regras globais (NF-e padrão, email, CPF/CNPJ)
SELECT * FROM rules WHERE scope = 'global' AND doc_type = 'nfe';

-- Regras de um cliente específico (layout customizado)
SELECT * FROM rules WHERE scope = 'client' AND client_id = '...';
```

Regras de cliente sobrepõem globais para o mesmo `field_name` (priority menor = prioridade maior).

### Cache de regras

Regras são cacheadas no Redis com TTL de 5 minutos por chave `rules:{doc_type}:{client_id}`. Invalidado automaticamente quando uma regra é promovida ou desativada.

---

## Adicionando novas regras manualmente

Edite `seed/rules.json` e rode `python seed/load_rules.py`. O script é idempotente — não duplica regras existentes.

Campos de uma regra:

```json
{
  "doc_type": "nfe",
  "field_name": "inscricao_estadual",
  "scope": "global",
  "pattern": "Inscri[çc][aã]o\\s+Estadual[:\\s]+(\\d[\\d\\.\\-]+)",
  "capture_group": 1,
  "normalizer": "digits_only",
  "priority": 10,
  "confidence_baseline": 0.88,
  "origin": "handcrafted"
}
```

| Normalizer | Efeito |
|---|---|
| `strip` | Remove espaços nas bordas |
| `digits_only` | Remove tudo exceto dígitos |
| `date_iso` | Converte DD/MM/YYYY → YYYY-MM-DD |
| `currency_brl` | `1.250,50` → `1250.50` |
| `none` | Sem transformação |

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Chave Anthropic (obrigatória) |
| `GROQ_API_KEY` | — | Chave Groq (obrigatória) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | URL do Postgres |
| `REDIS_URL` | `redis://localhost:6379` | URL do Redis |
| `THRESHOLD_L1` | `0.85` | Confiança mínima para parar no Nível 1 |
| `THRESHOLD_L2` | `0.82` | Confiança mínima para parar no Nível 2 |
| `THRESHOLD_L3` | `0.78` | Confiança mínima para parar no Nível 3 |
| `LEARNING_LOOP_AUTO_PROMOTE` | `0.90` | Confiança para promover regra direto |
| `LEARNING_LOOP_QUEUE_HUMAN` | `0.70` | Abaixo disso vai para revisão humana |
| `LEARNING_LOOP_ACCUMULATE_N` | `3` | Docs necessários para promover regra média |
| `MAX_FILE_SIZE_MB` | `50` | Tamanho máximo de upload |
| `RULE_CACHE_TTL_SECONDS` | `300` | TTL do cache de regras no Redis |

---

## Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=app tests/

# Apenas unitários (sem dependências externas)
pytest tests/unit/
```

---

## Roadmap

### MVP (atual)
- [x] Pipeline de 4 níveis com thresholds configuráveis
- [x] Detecção automática de tipo de documento
- [x] Regras seed para NF-e, currículo e conta de luz
- [x] Cache de regras no Redis
- [x] API REST: `/extract`, `/feedback`
- [x] Worker assíncrono com ARQ
- [ ] `run_learning_loop` — geração e validação de regras candidatas
- [ ] `GET /v1/documents/{id}` — histórico de extrações

### Fase 2
- [ ] RAG integrado — `POST /v1/query`
- [ ] Validação de consistência interna (soma de itens vs total NF)
- [ ] Alertas configuráveis (vencimento, CNPJ novo, consumo acima da média)
- [ ] Dashboard com métricas por cliente

### Fase 3
- [ ] SLM próprio (Qwen2.5-7B na GPU)
- [ ] Fine-tuning com dados acumulados por segmento
- [ ] SDK Python e Node.js
