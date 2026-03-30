# DocIntelligence — Decisões de Produto

## Proposta de valor

Extração de dados estruturados de qualquer documento (PDF, imagem) via API.
Diferencial: sistema aprende com cada documento processado e gera regras regex automáticas, reduzindo custo ao longo do tempo.

---

## Benchmark de preços (concorrentes)

| Serviço | Preço por doc | Free tier | Obs |
|---|---|---|---|
| AWS Textract (Analyze Expense) | R$ 0,08 | 100 docs/mês (3 meses) | Pay-as-you-go |
| Google Document AI (Invoice) | R$ 0,06 | Nenhum | Pay-as-you-go |
| Azure Document Intelligence | R$ 0,06 | 500 docs/mês permanente | Pay-as-you-go |
| Mindee | R$ 0,58 | 250 docs/mês | Planos mensais |
| Docparser | R$ 0,58 | Trial 14 dias | Foco em templates |
| Veryfi | R$ 1,16 | 100 docs/mês | Forte em mobile |

### Nosso custo de operação

| Nível ativado | Custo real por doc |
|---|---|
| L1 + L2 (pdfplumber + regex) | R$ 0,00 |
| L3 (Groq Llama 3.3 70B) | R$ 0,001 |
| L4 (fallback Groq) | R$ 0,017 |
| **Média ponderada** | **~R$ 0,003** |

O learning loop faz com que mais documentos sejam resolvidos em L1/L2 ao longo do tempo, reduzindo o custo operacional progressivamente.

---

## Planos

| Plano | Preço/mês | Docs incluídos | Custo unitário cliente | Margem estimada |
|---|---|---|---|---|
| **Free** | R$ 0 | 30 docs | — | Aquisição |
| **Starter** | R$ 97 | 500 docs | R$ 0,19/doc | ~98% |
| **Pro** | R$ 297 | 2.000 docs | R$ 0,15/doc | ~98% |
| **Enterprise** | Sob consulta | Ilimitado | Negociado | — |

Excedente: R$ 0,30/doc em todos os planos pagos.

---

## Fluxo do usuário técnico (developer)

```
1. Acessa landing page
2. Lê proposta de valor + vê demo ao vivo
3. Clica "Começar grátis" → formulário (nome, email, empresa)
4. Recebe email com API key (por enquanto aprovação manual)
5. Lê documentação → testa no playground
6. Integra na aplicação
7. Acompanha uso no dashboard
```

**Endpoints que precisa:**
- `POST /v1/extract` — envia documento
- `GET /v1/extract/jobs/{id}` — polling do resultado
- `POST /v1/feedback` — corrige campo extraído errado
- `GET /v1/account/usage` — uso do mês
- `POST /v1/account/rotate-key` — rotaciona API key

---

## Fluxo do usuário não-técnico (contador, analista, RH)

```
1. Acessa landing page (linguagem simples, sem jargão técnico)
2. Testa grátis no playground — arrasta PDF, vê campos extraídos
3. Plano pago → acesso ao dashboard
4. Faz upload em lote pelo dashboard
5. Baixa resultados em CSV/Excel
6. Se precisar integrar com ERP → botão "Fale conosco"
```

**Regra:** integração com ERP (TOTVS, SAP, Omie, Conta Azul) é serviço consultivo.
Não construir conectores prontos agora — cobra projeto separado por cliente.

---

## Stack de tecnologia

### Backend (já implementado)
- FastAPI + SQLModel (PostgreSQL em prod, SQLite em dev)
- ARQ (filas de job com Redis)
- Groq `llama-3.3-70b-versatile` — extração
- Groq `llama-3.1-8b-instant` — validação de regex
- Cloudflare R2 (storage de arquivos)

### Frontend
- **Next.js 15** com `output: standalone` (imagem Docker ~120MB)
- **Tailwind CSS v4**
- **shadcn/ui** — componentes
- **Fumadocs** — seção `/docs` com Cmd+K e busca local
- **Framer Motion** — animações no hero
- **Clerk** — autenticação do dashboard

### Infra (VPS)
- Docker Compose com 4 serviços: `api`, `worker`, `web`, `db`, `redis`
- nginx como reverse proxy (termina SSL, roteia `/` para web, `/v1` para api)
- Certbot para certificado SSL automático

---

## Estrutura de páginas

```
/                       Landing page
/docs                   Documentação pública com Cmd+K
/docs/quickstart        Primeiros passos
/docs/api-reference     Referência completa dos endpoints
/docs/examples          Exemplos por tipo de documento
/playground             Testa extração sem precisar de conta
/dashboard              Área autenticada
/dashboard/keys         API keys + rotação
/dashboard/usage        Uso do mês + gráfico
/dashboard/logs         Histórico de documentos processados
```

---

## Roadmap

**Fase 1 — MVP (agora)**
- [ ] Landing page com demo ao vivo
- [ ] Documentação com Cmd+K
- [ ] Dashboard: API key, uso, histórico
- [ ] Playground público

**Fase 2 — após primeiros clientes**
- [ ] Self-service (cadastro + Stripe)
- [ ] Export CSV/Excel
- [ ] Webhooks configuráveis
- [ ] Admin panel (gerenciar clientes, ver logs)

**Fase 3 — escala**
- [ ] Conectores ERP (TOTVS, Omie) como produto separado
- [ ] White-label para parceiros
