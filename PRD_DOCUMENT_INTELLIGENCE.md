# PRD — Document Intelligence Platform

**Status**: Conceito
**Data**: 2026-03-29
**Autor**: Rafael Renton

---

## 1. Visão do Produto

Uma plataforma de extração e inteligência sobre documentos que aprende continuamente, reduz custo por documento com o tempo, e entrega valor além da extração simples — competindo diretamente com AWS Textract, Google Document AI e Azure Form Recognizer com preço menor e funcionalidades superiores.

**Posicionamento**: Não é uma ferramenta de extração. É inteligência sobre documentos.

---

## 2. Problema

Soluções existentes (AWS Textract, Google Document AI) cobram por documento independente do resultado e não aprendem — o 100.000º documento custa igual ao primeiro. Empresas com alto volume pagam caro por algo que poderia ser resolvido localmente com regras simples.

Além disso, extrair texto não é suficiente — o valor real está em entender o que foi extraído, validar consistência e responder perguntas sobre o conteúdo.

---

## 3. Solução

Uma plataforma com três camadas de valor:

1. **Extração inteligente** — pipeline que aprende e fica mais barato com o uso
2. **Validação** — detecta inconsistências no próprio documento
3. **Inteligência** — RAG integrado para consultas, alertas e comparações

---

## 4. Casos de Uso Iniciais

| Documento | Campos extraídos | Valor adicional |
|---|---|---|
| Nota Fiscal (NF-e) | CNPJ, valor total, data, itens, impostos | Valida total vs soma de itens, alerta CNPJ novo |
| Conta de luz | Consumo, valor, vencimento, distribuidora | Alerta consumo acima da média histórica |
| Currículo | Nome, cargo, skills, experiências, formação | Score ATS, compatibilidade com vaga |
| Contrato | Partes, valor, prazo, cláusulas-chave | RAG para perguntas, diff entre versões |

---

## 5. Arquitetura do Pipeline

### 5.1 Pirâmide de extração (custo crescente)

```
Nível 1 — Extração binária do PDF         (grátis, instantâneo)
Nível 2 — Regras aprendidas (regex)        (grátis, instantâneo)
Nível 3 — SLM local/dedicado              (custo de hardware)
Nível 4 — IA externa (Claude, Gemini)     (custo por token)
Nível 5 — Validação humana                (último recurso)
```

Cada nível só ativa se o anterior falhou ou retornou confiança baixa.

### 5.2 Loop de aprendizado

```
Documento entra
    ↓
Tenta extração local (níveis 1 e 2)
    ↓ falhou ou baixa confiança
Modelo A extrai + explica como extraiu
    ↓
Gera regra nova
    ↓
Aplica regra no mesmo documento
    ↓
Modelo B valida: resultado da regra == resultado do Modelo A?
    ↓
Validação estrutural: formatos, checksums, consistência interna
    ↓
Confiança alta  → salva regra, usa imediatamente
Confiança média → acumula N documentos do mesmo tipo antes de salvar
Confiança baixa → fila de revisão humana (< 5% dos casos)
    ↓
Humano valida → par (documento, ground truth) realimenta geração de regra
```

### 5.3 Isolamento de regras por cliente

- Regras específicas de layout ficam isoladas por cliente
- Padrões genéricos (NF-e padrão, layouts regulados) são compartilhados entre todos
- Cliente A não vaza dados para cliente B

### 5.4 Modelos

| Papel | Modelo sugerido | Motivo |
|---|---|---|
| Extração + geração de regra | Claude Sonnet / GPT-4o | Melhor compreensão de layout |
| Validação de regra | Gemini Flash / Llama via Groq | Rápido, barato, modelo diferente evita viés |
| SLM local (médio prazo) | Phi-3 / Qwen2.5 | Roda em GPU dedicada, zero custo por token |

---

## 6. Funcionalidades do Produto

### MVP (fase 1)
- [ ] Detecção automática de tipo de documento
- [ ] Extração binária de PDF nativo
- [ ] OCR para PDFs escaneados e imagens
- [ ] Extração estruturada em JSON com score de confiança por campo
- [ ] Loop de aprendizado com dois modelos
- [ ] API REST simples (POST /extract)

### Fase 2
- [ ] RAG integrado — perguntas sobre documentos
- [ ] Validação de consistência interna do documento
- [ ] Alertas configuráveis (vencimento, valor acima da média, CNPJ novo)
- [ ] Dashboard do cliente com histórico e métricas

### Fase 3
- [ ] Comparação entre versões do mesmo documento
- [ ] Fine-tuning do SLM com dados acumulados por segmento
- [ ] Preço por documento decrescente automático conforme aprendizado
- [ ] SDK (Python, Node.js)

---

## 7. API

```
POST /v1/extract
  body: { file: binary, doc_type: string (opcional), fields: string[] (opcional) }
  returns: { data: {}, confidence: {}, doc_type: string, processing_level: int }

POST /v1/query
  body: { document_id: string, question: string }
  returns: { answer: string, source_excerpt: string }

GET /v1/documents/{id}
  returns: histórico de extrações, regras aprendidas, confiança

POST /v1/feedback
  body: { document_id: string, field: string, correct_value: string }
  returns: confirmação — realimenta o sistema
```

---

## 8. Precificação

### Modelo por volume mensal

| Volume | Preço por documento |
|---|---|
| até 1.000 | R$ 0,08 |
| 1.001 – 10.000 | R$ 0,05 |
| 10.001 – 100.000 | R$ 0,03 |
| 100.000+ | negociado |

### Diferenciais vs concorrentes

- **50-80% mais barato** que AWS Textract e Google Document AI
- **Preço decrescente** — conforme o sistema aprende, o custo por documento cai
- **RAG incluído** — concorrentes cobram separado por consultas
- **Alertas e validação** — não existe nos concorrentes

---

## 9. Go-to-Market

### Fase 0 — Uso interno (agora)
- Radar de Empregos consome a API para processar currículos
- Valida o pipeline com dados reais sem pressão de cliente externo

### Fase 1 — Primeiros clientes externos
- Foco em NF e contas de luz (alta padronização, dor real, volume alto)
- Empresas médias que processam centenas a milhares de docs/mês
- Preço abaixo dos concorrentes internacionais

### Fase 2 — Expansão
- Contratos + RAG (diferencial claro)
- Documentos de RH (outros produtos de recrutamento)
- API pública com self-service

---

## 10. Infraestrutura

### Curto prazo (até 50k docs/mês)
- VPS atual para API e regras locais
- Groq ou Together.ai para SLM via API (custo por token)
- Custo estimado: ~R$ 200-500/mês

### Médio prazo (50k - 500k docs/mês)
- GPU dedicada (Runpod RTX 4090, ~$320/mês)
- SLM próprio rodando 24/7
- IA externa apenas para documentos genuinamente novos

### Longo prazo (500k+ docs/mês)
- Fine-tuning do SLM com dados acumulados por segmento
- A maioria dos documentos resolvida localmente, custo marginal próximo de zero

---

## 11. Métricas de Sucesso

| Métrica | Meta fase 1 |
|---|---|
| % documentos resolvidos localmente | > 70% após 3 meses |
| Confiança média de extração | > 90% |
| Custo por documento | < R$ 0,02 em média |
| Tempo de resposta | < 3s por documento |
| Churn de clientes | < 5% mensal |

---

## 12. Riscos

| Risco | Mitigação |
|---|---|
| Regras geradas com viés de modelo | Validação com dois modelos diferentes |
| Layout do documento muda sem aviso | Queda de confiança detecta automaticamente, aciona IA |
| Volume alto antes de GPU própria | Groq/Together.ai escalam sob demanda |
| Concorrentes reduzem preço | Diferencial é o aprendizado + RAG, não só preço |
