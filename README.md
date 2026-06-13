# CdC-Search — Diretório de Empresas de Casal de Cambra

Agente que recolhe empresas de **Casal de Cambra (Sintra)** a partir do
**Google Maps** (Google Places API) e do **racius.com**, categoriza-as por tipo
(restaurante, farmácia, mercearia, café, …) e serve um **site de diretório
dinâmico** (FastAPI). Corre **1×/dia** para encontrar novas empresas.

Pensado para deploy no **Hetzner** com Docker Compose.

---

## Arquitetura

```
Caddy (HTTPS público)  ─►  web (FastAPI + Jinja2)  ─►  SQLite (volume)
                                                          ▲
ingest (cron 1×/dia) ─► pipeline:                         │
   Google Places API ─► racius.com ─► LLM gateway ────────┘
                          (enriquecimento)  (categorização, rede interna)
```

- **web** — aplicação FastAPI que serve o diretório (categorias, fichas de
  empresa, pesquisa) e uma API JSON de leitura em `/api`.
- **ingest** — pipeline diário idempotente: recolhe, classifica, faz upsert,
  enriquece e faz soft-delete de empresas que fecharam.
- **gateway** — [free-llm-gateway](https://github.com/MrFadiAi/free-llm-gateway),
  usado **só** para categorizar empresas que a Google não classifica de forma
  clara. Corre na **rede interna** do Docker, **nunca exposto à internet**.

### Porquê estas escolhas

| Decisão | Escolha | Motivo |
|---|---|---|
| Dados Maps | Google Places API | Oficial e fiável; volume mínimo (1 vila, 1×/dia) cabe no crédito gratuito |
| LLM gateway | free-llm-gateway (Python) | Fallback automático entre providers, rate-limiting por chave, mesmo runtime do resto |
| Website | FastAPI dinâmico | Pesquisa server-side e API; fácil de evoluir |
| Base de dados | SQLite (WAL) | Suficiente para o volume; zero manutenção |

**Segurança:** só o Caddy publica portas. O `web` e o `gateway` não expõem
portas para fora. O LLM só recebe **texto público** (nome + tipos da empresa);
nenhum dado sensível sai do servidor. O dashboard do gateway não é publicado.

---

## Pré-requisitos

1. **Chave da Google Places API (New)**
   - Cria um projeto em <https://console.cloud.google.com>.
   - Ativa **Places API (New)**.
   - Cria uma chave de API e restringe-a (por API e, idealmente, por IP do
     servidor Hetzner).
   - Coloca-a em `GOOGLE_MAPS_API_KEY` no `.env`.

2. **Chaves dos providers do LLM** (Groq + NVIDIA NIM)
   - O gateway recebe as chaves em `gateway/.env`:
     - `GROQ_KEY` — a tua chave Groq
     - `NVIDIA_NIM_KEY` — a tua chave NVIDIA NIM
     - `MASTER_KEY` — chave interna do gateway; tem de ser **igual** a
       `LLM_GATEWAY_API_KEY` no `.env` raiz.
   - Há um template pronto: `deploy/gateway.env.example`.
   - O modelo lógico `LLM_MODEL=llama-3.3-70b` usa o **Groq como primário** e o
     **NVIDIA NIM como fallback** (definido em `gateway/models.yaml` — confirma
     a cadeia, ver template).
   - Se não quiseres LLM, define `LLM_ENABLED=false` no `.env` — a
     categorização usa apenas os tipos da Google.

---

## Arranque rápido (local)

```bash
cp .env.example .env          # preenche GOOGLE_MAPS_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Servir o site (cria a BD automaticamente):
uvicorn app.main:app --reload

# Correr a recolha uma vez:
python -m scripts.run_ingest
```

Abre <http://localhost:8000>.

---

## Deploy no Hetzner (Docker Compose)

```bash
# 1. Clonar e configurar
git clone <este-repo> /opt/CdC-Search && cd /opt/CdC-Search
cp .env.example .env
nano .env                      # GOOGLE_MAPS_API_KEY, SITE_BASE_URL, ...
nano Caddyfile                 # troca example.com pelo teu domínio

# 2. LLM gateway (Groq + NVIDIA NIM)
git clone https://github.com/MrFadiAi/free-llm-gateway.git gateway
cp deploy/gateway.env.example gateway/.env
nano gateway/.env              # GROQ_KEY, NVIDIA_NIM_KEY, MASTER_KEY
# confirma que gateway/models.yaml mapeia "llama-3.3-70b" -> groq + nvidia

# 3. Arrancar
docker compose up -d                      # caddy + web
docker compose --profile llm up -d        # + gateway (se configurado)

# 4. Primeira recolha
docker compose --profile ingest run --rm ingest

# 5. Recolha diária (cron do host)
crontab deploy/crontab.example            # ajusta o caminho do projeto
```

O site fica disponível no teu domínio com HTTPS automático (Caddy/Let's
Encrypt).

---

## Como funciona o pipeline

1. **Recolha** — corre várias queries por tipo ("restaurantes", "farmácias",
   …) na Google Places API, restritas a um círculo à volta de Casal de Cambra
   (`TARGET_*` no `.env`), com paginação. Desduplica por `place_id`.
2. **Categorização** — primeiro pelos tipos da Google
   (`app/categories.py`); se não chegar, recorre ao LLM (`app/ingest/llm.py`).
3. **Upsert** — insere novas / atualiza existentes por `place_id`
   (idempotente). Atualiza `last_seen_at`.
4. **Enriquecimento** — procura no racius.com NIF e link da ficha
   (best-effort; falha em silêncio se o site bloquear).
5. **Soft-delete** — empresas que deixaram de aparecer (ou marcadas
   `CLOSED_PERMANENTLY`) ficam `active = false`.
6. **Auditoria** — cada execução fica registada em `ingest_runs`.

## Personalizar

- **Localização / raio** — `TARGET_*` no `.env`.
- **Categorias** — edita `app/categories.py` (slug, nome, ícone e tipos da
  Google associados).
- **Queries de pesquisa** — `SEARCH_QUERIES` em
  `app/ingest/sources/google_places.py`.

## Avisos

- O scraping do **racius.com** é frágil e dependente da estrutura do site; é
  opcional (`RACIUS_ENABLED`) e nunca interrompe o pipeline.
- Respeita os Termos de Serviço das fontes e a legislação aplicável (RGPD)
  ao publicar dados de empresas.

## Estrutura

```
app/
  config.py            # configuração (.env)
  database.py          # SQLAlchemy + SQLite (WAL)
  models.py            # Business, Category, IngestRun
  categories.py        # categorias + mapeamento dos tipos da Google
  main.py              # app FastAPI
  routes/web.py        # páginas HTML
  routes/api.py        # API JSON de leitura
  templates/           # Jinja2
  static/style.css
  ingest/
    pipeline.py        # orquestração do pipeline diário
    llm.py             # categorização via gateway (fallback)
    dedup.py           # correspondência difusa de nomes
    sources/
      google_places.py # Google Places API (New)
      racius.py        # enriquecimento racius.com
scripts/run_ingest.py  # entrypoint do cron
deploy/crontab.example
docker-compose.yml · Dockerfile · Caddyfile
```
