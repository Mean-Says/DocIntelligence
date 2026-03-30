# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Dependências
pip install -e ".[dev]"

# Serviços locais
docker compose up -d db redis

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"  # nova migration

# Seed de regras
python seed/load_rules.py

# API (dev)
uvicorn app.main:app --reload

# Worker ARQ (terminal separado)
python -m arq app.workers.arq_settings.WorkerSettings

# Testes
pytest
pytest tests/unit/
pytest tests/unit/test_matcher.py::test_name -v
pytest --cov=app tests/

# Lint
ruff check app/
ruff format app/
```

## Arquitetura

### Fluxo de uma requisição

`POST /v1/extract` → upload R2 → cria `Document` (status=pending) → enfileira ARQ job → retorna 202.

O worker ARQ executa `process_document()` em `app/workers/tasks.py`, que chama `orchestrator.run()`. Ao finalizar, salva em `Extraction` e, se usou AI (nível ≥ 3), enfileira `run_learning_loop()`.

### Pipeline de extração (`app/pipeline/orchestrator.py`)

Arquivo mais crítico. Executa 4 níveis em sequência, parando assim que a confiança supera o threshold do nível:

| Nível | Arquivo | Threshold padrão |
|---|---|---|
| 1 — pdfplumber + padrões universais | `levels/level1_binary.py` | 0.85 |
| 2 — regras regex do banco | `rule_engine/matcher.py` | 0.82 |
| 3 — Groq / Llama 3.3 70B | `levels/level3_slm.py` | 0.78 |
| 4 — Claude Sonnet | `levels/level4_claude.py` | sempre aceita |

OCR (`utils/ocr.py`) é ativado entre os níveis 2 e 3 quando o arquivo é PDF escaneado ou imagem.

A confiança geral é calculada em `utils/confidence.py` como média ponderada por campo. Campos required ausentes penalizam o score.

### Rule engine (`app/rule_engine/`)

`loader.py` busca regras do Postgres, serializa e armazena no Redis (TTL 5min, chave `rules:{doc_type}:{client_id}`). Na leitura do cache, reconstrói objetos `re.Pattern`.

`matcher.py` aplica as regras no texto. Nunca sobrescreve campo já encontrado com confiança maior.

Regras têm dois escopos:
- `global` — compartilhadas entre todos os clientes (padrões de NF-e federal, email, CPF/CNPJ)
- `client` — isoladas por cliente, sobrepostas às globais (priority=0 por convenção)

Ao adicionar ou desativar uma regra, chamar `loader.invalidate_cache()` para limpar o Redis.

### Learning loop (`app/workers/tasks.py`)

`run_learning_loop` está como stub (TODO). Quando implementado, deve:
1. Carregar `raw_text` do R2 e campos da `Extraction`
2. Chamar Claude para gerar regex candidata por campo
3. Chamar Groq para validar a candidata
4. Salvar `RuleCandidate` com `validation_status` adequado
5. Promover para `Rule` se `validation_confidence >= settings.learning_loop_auto_promote`

### Models (`app/models/`)

`SQLModel` unifica ORM e schema Pydantic. A tabela `rules` é a mais crítica — qualquer alteração de schema afeta o loop de aprendizado. `rule_candidates` é a fila de regras aguardando promoção. Campos JSON (`fields`, `confidence_scores`) usam `JSONB` do Postgres via `sa_column=Column(JSONB)`.

### Configuração

Todos os thresholds e parâmetros do pipeline vivem em `app/config.py` (pydantic-settings). Nunca hardcode valores de threshold — use `settings.*`. Thresholds podem ser ajustados via `.env` sem redeploy.

### Adicionando suporte a novo tipo de documento

1. Adicionar entrada em `DocumentType` (`app/models/document.py`)
2. Adicionar `REQUIRED_FIELDS` e `FIELD_WEIGHTS` em `utils/confidence.py`
3. Adicionar keywords de detecção em `pipeline/detector.py` (`_DOC_TYPE_SIGNALS`)
4. Adicionar regras seed em `seed/rules.json` e rodar `python seed/load_rules.py`
