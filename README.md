# Licensing API

API de licenciamento de software: **chaves assinadas digitalmente (Ed25519)** com **validação offline** no cliente e **ativação online** por máquina no servidor.

Stack: Python 3.12 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic · Docker Compose · uv.

---

## Como funciona (o modelo de licença)

Existem dois mecanismos que se complementam:

### 1. Chave assinada offline
Cada licença emitida é uma string assinada com **Ed25519** (criptografia assimétrica):

```
LIC1.<base64url(payload JSON)>.<base64url(assinatura)>
```

O payload contém os dados da licença:

| Campo | Significado |
|---|---|
| `iss` | emissor (identifica sua API) |
| `sub` | nome do cliente |
| `lic` | UUID da licença no banco |
| `iat` | momento da emissão |
| `exp` | expiração (epoch); determinada pelo pacote de **1, 2, 3 ou 5 anos** |
| `tier` | tipo de licença (standard/premium/...) |
| `max` | limite de ativações |

**A assinatura usa a chave privada que só existe no servidor.** O software do cliente embute apenas a **chave pública** e verifica a assinatura localmente — funciona sem internet. Se alguém forjar uma chave, a assinatura não confere. É a mesma ideia usada em licenças de software comercial.

### 2. Ativação online
O cliente envia a chave + um identificador de máquina (`machine_id`) para `POST /api/v1/activate`. O servidor:

1. verifica a assinatura da chave;
2. confere se a licença existe no banco, não está revogada e não expirou;
3. conta as ativações ativas e registra a máquina (respeitando `max_activations`);
4. responde com a ativação criada.

Isso dá revogação e controle de máquinas — coisas que uma chave offline sozinha não tem.

> Não existe licença inquebrável. O objetivo é elevar o custo da pirataria (assinatura) e dar controle (revogação, limite de máquinas). Quem consegue o binário sempre pode tentar extrair a chave pública — a robustez final depende de ofuscação no cliente, o que foge ao escopo desta API.

---

## Segurança aplicada

| Camada | Técnica |
|---|---|
| Assinatura das licenças | **Ed25519** (PyNaCl) |
| Senha dos admins | **Argon2** (`argon2-cffi`) |
| Sessão dos admins | **JWT HS256** com expiração (`pyjwt`) |
| Rotas públicas | **Rate limiting** por IP (slowapi) |
| Transporte | sempre **HTTPS** em produção (reverse proxy) |
| Segredos | fora do código, via variáveis de ambiente / `.env` |

---

## Estrutura

```
licensing-api/
├── app/
│   ├── main.py                # FastAPI, CORS, rate limit, rotas
│   ├── core/
│   │   ├── config.py          # Settings (lê .env)
│   │   ├── database.py        # engine async + sessão
│   │   ├── security.py        # Argon2 + JWT
│   │   ├── signing.py         # assina/valida chaves Ed25519
│   │   └── ratelimit.py       # wrapper do slowapi
│   ├── models/                # SQLAlchemy: Admin, License, Activation
│   ├── schemas/               # Pydantic: entrada/saída das rotas
│   ├── services/              # lógica de negócio (emissão/ativação)
│   └── api/
│       ├── deps.py            # depende do admin autenticado
│       └── routes/
│           ├── auth.py        # login + me
│           ├── licenses.py    # CRUD de licenças (admin)
│           └── activations.py # ativar/validar (público)
├── alembic/                   # migrações de banco
├── cli/main.py                # painel CLI (typer + rich)
├── scripts/
│   ├── generate_keys.py       # gera o par Ed25519
│   └── create_admin.py        # cria usuário admin
├── tests/                     # pytest (assinatura + API)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml             # dependências (uv)
```

### Campos da licença

| Campo | Descrição |
|---|---|
| `customer_name` | **licenciado** (empresa ou pessoa titular da licença) |
| `email` | e-mail do licenciado |
| `contact_name` | **contato para renovação** (geralmente uma pessoa) |
| `contact_email` | e-mail do contato |
| `contact_phone` | telefone do contato |
| `tier` | tipo de licença (standard/premium/enterprise) |
| `validity_years` | pacote comprado: **1, 2, 3 ou 5 anos** (define `expires_at` na emissão) |
| `expires_at` | data de expiração (calculada do pacote; renovação soma ao vencimento atual) |
| `max_activations` | limite de máquinas ativas |
| `revoked` | se a licença está revogada |

Os campos de contato servem para você localizar e negociar a **renovação** e **não entram na chave assinada** — alterá-los não invalida a chave que os clientes já têm.

---

## Como rodar

### 1. Subir a stack (PostgreSQL + migração + API)

```bash
docker compose up -d --build
```

- `db` → PostgreSQL 17 (porta 5432)
- `migrate` → roda `alembic upgrade head` (cria as tabelas) e encerra
- `api` → FastAPI na porta **8000**

### 2. Criar o usuário admin

```bash
docker compose exec -T api uv run scripts/create_admin.py --username admin --password 'Senha@Fort3'
```

### 3. Testar

```bash
# saúde
curl http://localhost:8000/healthz

# documentação interativa (Swagger)
# http://localhost:8000/docs
```

---

## Endpoints

### Públicos

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/auth/login` | login do admin → retorna JWT |
| POST | `/api/v1/activate` | ativa uma máquina com a chave (rate: 10/min) |
| POST | `/api/v1/validate` | valida a chave no servidor (rate: 30/min) |

### Admin (cabeçalho `Authorization: Bearer <token>`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/admin/admins` | cria usuário administrador |
| GET | `/api/v1/admin/admins` | lista administradores |
| GET | `/api/v1/admin/admins/{id}` | detalhe de um admin |
| PATCH | `/api/v1/admin/admins/{id}` | edita usuário/senha de um admin |
| DELETE | `/api/v1/admin/admins/{id}` | exclui admin (não permite excluir a si mesmo) |
| POST | `/api/v1/admin/licenses` | emite licença (pacote de **1/2/3/5 anos**) → retorna a **chave assinada** |
| GET | `/api/v1/admin/licenses` | lista licenças |
| GET | `/api/v1/admin/licenses/{id}` | detalhe de uma licença |
| GET | `/api/v1/admin/licenses/{id}/key` | recupera a chave assinada |
| PATCH | `/api/v1/admin/licenses/{id}` | edita (re-assina a chave só se cliente/tier/max/expiração mudarem) |
| POST | `/api/v1/admin/licenses/{id}/renew` | renova somando **1/2/3/5 anos** ao vencimento atual (re-assina a chave) |
| DELETE | `/api/v1/admin/licenses/{id}` | exclui |
| GET | `/api/v1/admin/licenses/{id}/activations` | lista ativações da licença |
| DELETE | `/api/v1/admin/licenses/{id}/activations/{aid}` | revoga uma ativação (libera a máquina) |
| GET | `/api/v1/auth/me` | quem é o admin logado |

### Exemplo do fluxo

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Senha@Fort3"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# emitir licença (guarde a chave retornada no campo "key")
curl -s -X POST http://localhost:8000/api/v1/admin/licenses \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"customer_name":"Empresa XPTO","email":"contato@xpto.com","tier":"enterprise","max_activations":2}'

# cliente ativa uma máquina
curl -s -X POST http://localhost:8000/api/v1/activate \
  -H 'Content-Type: application/json' \
  -d '{"license_key":"LIC1.eyJpc3Mi...","machine_id":"maq-a"}'

# cliente valida
curl -s -X POST http://localhost:8000/api/v1/validate \
  -H 'Content-Type: application/json' \
  -d '{"license_key":"LIC1.eyJpc3Mi..."}'
```

---

## Painel CLI (`licensing-cli`)

Acompanha um painel de terminal que consome a API (usando o token guardado localmente).

### Instalação / uso

```bash
uv sync                                   # instala o comando licensing-cli
uv run licensing-cli --help               # lista os comandos
```

### Sessão

```bash
licensing-cli login --base-url http://localhost:8000 --username admin
licensing-cli whoami
licensing-cli logout
```

### Administradores

```bash
licensing-cli admins list
licensing-cli admins create --username gestor
licensing-cli admins password <id>        # troca senha (pergunta, escondida)
licensing-cli admins delete <id>
```

### Licenças

```bash
licensing-cli licenses list
licensing-cli licenses show <id>
licensing-cli licenses key <id>           # recupera a chave assinada (saída crua)
licensing-cli licenses create --customer "Empresa XPTO" --email contato@xpto.com --tier enterprise --max-activations 2 --anos 2
licensing-cli licenses create --customer "Empresa Acme LTDA" --contact-name "Maria Silva" --contact-email maria@acme.com --contact-phone "+55 11 99999-0000" --anos 5
licensing-cli licenses renew <id> --anos 2   # estende do vencimento atual
licensing-cli licenses revoke <id>        # revoga (a chave NÃO muda)
licensing-cli licenses revoke <id> --no-revoke   # desrevoga
licensing-cli licenses activations <id>   # máquinas ativas
licensing-cli licenses revoke-activation <id> <activation-id>   # libera vaga
licensing-cli licenses delete <id>
```

### Como cliente (testar ativação/validação)

```bash
licensing-cli activate --key "LIC1...." --machine "maq-a"
licensing-cli validate --key "LIC1...."
licensing-cli stats
```

O token é salvo em `~/.config/licensing-cli/config.json`. Em sessão expirada, o CLI pede para você rodar `login` novamente.

---

## Integração no software do cliente

O cliente deve:
1. **validar offline** a assinatura com a chave pública (funciona sem internet);
2. **ativar online** uma vez por máquina;
3. **revalidar periodicamente** com `POST /validate` (detecta revogação).

Exemplo mínimo de validação offline em Python:

```python
import base64, json
import nacl.signing

PUBLIC_KEY_B64 = "vONy5XOTy2ABVWyIb5v7kncmKkhnP3HHdbeA6kqRkO0="  # embutida no binário

def b64u_decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def verificar_licenca(chave):
    prefix, body, sig = chave.split(".")
    if prefix != "LIC1":
        raise ValueError("chave invalida")
    vk = nacl.signing.VerifyKey(base64.b64decode(PUBLIC_KEY_B64))
    vk.verify(body.encode(), b64u_decode(sig))   # levanta se for falsa
    return json.loads(b64u_decode(body))
```

> A **chave pública** pode ser publicada sem risco; só a **privada** é segredo. Em produção troque pelo par gerado por você e **não** use a deste repositório.

---

## Testes

Os testes usam SQLite em memória (sem precisar do Postgres):

```bash
uv sync
uv run pytest -q
```

Cobrem: assinatura/verificação, chave adulterada/expirada, login, emissão, limite de ativações, revogação, liberação de vaga, validação de chave forjada e CRUD de administradores (criar, editar senha, excluir, sem exclusão do próprio usuário).

---

## Produção — checklist

1. **Gerar novo par de chaves:** `uv run scripts/generate_keys.py` e trocar no `.env`.
2. **Trocar `JWT_SECRET`** por um valor aleatório longo (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. **Trocar senha do Postgres** no `docker-compose.yml` (e em `DATABASE_URL`).
4. **HTTPS** via reverse proxy (nginx/Caddy/Traefik) na frente da API.
5. Restringir `CORS_ORIGINS` aos seus domínios.
6. Backup do Postgres (volume `pgdata`).
7. Guardar a **chave privada** com segurança; só a pública vai para os clientes.

---

## Comandos úteis

```bash
docker compose down            # derruba tudo
docker compose up -d --build   # reconstrói e sobe
docker compose logs -f api     # logs da API
uv run scripts/create_admin.py --username admin --password 'Senha@Fort3'  # novo admin (local)
uv run alembic upgrade head    # aplica migrações (local)
```
