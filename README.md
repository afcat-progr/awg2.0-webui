Проект развивается и сделан при помощи Claude Code

# AmneziaWG WebUI

Веб-панель для управления **AmneziaWG 2.0** на одном VPS. Позволяет создавать
несколько серверов (интерфейсов `awg0`, `awg1`, …), клиентов в каждом из них,
выдавать им конфиги и QR-коды. Работает в Docker, доступ к панели — через
SSH-туннель.

```
┌─────────────── VPS (Docker) ───────────────┐
│  awg-webui (FastAPI + HTMX, :127.0.0.1:8080)│
│     ├── awg0  (10.8.0.1/24, :51820)         │
│     │     ├── phone-ivan  10.8.0.2          │
│     │     └── laptop-anna 10.8.0.3          │
│     └── awg1  (10.9.0.1/24, :51821)         │
│           └── ...                            │
└──────────────────────────────────────────────┘
        ▲ ssh -L 8080:localhost:8080 root@vps
   ваш браузер → http://localhost:8080
```

## Возможности

- **Серверы (интерфейсы):** создание/редактирование/удаление, вкл/выкл, авто-генерация ключей.
- **Полный набор настроек AmneziaWG 2.0:** `Jc, Jmin, Jmax, S1, S2, H1–H4`, MTU, DNS, порт, подсеть, WAN-интерфейс для NAT.
- **Клиенты:** авто-выдача IP из подсети, PresharedKey, AllowedIPs, DNS, keepalive.
- **Конфиги:** просмотр, скачивание `.conf`, **QR-код** для приложения AmneziaWG.
- **Применение к системе:** пишет `/etc/amnezia/amneziawg/awgN.conf` и делает `awg-quick up` / `awg syncconf` (горячая перезагрузка без разрыва других пиров).
- **Безопасность:** панель слушает только `127.0.0.1`, вход по логину/паролю (bcrypt), сессии в подписанных cookie.

## Требования на VPS

1. Linux VPS (Ubuntu/Debian рекомендуется), root-доступ.
2. **Установленный AmneziaWG** (ядро-модуль + userspace-инструменты) на хосте:
   ```bash
   sudo add-apt-repository ppa:amnezia/ppa
   sudo apt update
   sudo apt install amneziawg amneziawg-tools
   # проверка:
   which awg awg-quick
   ```
   Модуль ядра `amneziawg` должен загружаться на хосте (`modprobe amneziawg`).
3. Docker + Docker Compose.

> Без установленного на хосте AmneziaWG панель всё равно запустится, но в режиме
> «plain WireGuard» (fallback `wg`/`wg-quick`) — обфускация работать не будет.
> Для AWG 2.0 ставьте `amneziawg` на хост и используйте `docker-compose.override.yml`.

### ⚠️ Клиент подключается, но нет интернета / висит на «Connecting…»

Самая частая причина — **рассинхрон версий модуля ядра и userspace-инструментов**
AmneziaWG. PPA Amnezia иногда выкладывает модуль (`amneziawg-dkms`) старее, чем
`amneziawg-tools`. Они по-разному кодируют обфускацию (junk, S1–S4, H1–H4) →
handshake молча не проходит, даже локально.

**Признаки:** пакеты от клиента доходят (`tcpdump` видит UDP на порт), но в
`awg show` у пира нет `latest handshake`, а `transfer` = `0 B received`.

**Лечится пересборкой модуля из исходников под текущее ядро:**
```bash
sudo bash install-module.sh        # из этого репозитория
docker compose restart awg-webui
```
Скрипт ставит заголовки ядра, собирает модуль из официального GitHub Amnezia,
заменяет старый, перезагружает его и закрепляет пакет (`apt-mark hold`), чтобы
`apt upgrade` не вернул старую версию. Безопасно перезапускать после обновления
ядра.

Проверка после: подними сервер и убедись, что версии совпали, а handshake идёт:
```bash
modinfo amneziawg | grep version
awg --version
docker exec awg-webui awg show awg0   # у пира должен появиться latest handshake
```

## Запуск

```bash
git clone <repo> awg-webui && cd awg-webui

cp .env.example .env
# Сгенерируйте секрет и задайте пароль:
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
nano .env   # задайте ADMIN_USERNAME / ADMIN_PASSWORD, при желании PUBLIC_ENDPOINT

# (опционально) использовать awg с хоста:
cp docker-compose.override.yml.example docker-compose.override.yml

docker compose up -d --build
```

## Доступ к панели

Панель намеренно слушает только `127.0.0.1` и **не открыта наружу**. Заходите
через SSH-проброс порта со своей машины:

```bash
ssh -L 8080:localhost:8080 root@<IP_сервера>
# затем откройте в браузере:
#   http://localhost:8080
```

Логин/пароль — из `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).

## Как это работает

1. Создаёте **сервер** → панель генерирует ключи, пишет `awgN.conf`, поднимает интерфейс через `awg-quick up`.
2. Добавляете **клиента** → генерируются ключи, выдаётся свободный IP, `[Peer]` дописывается в конфиг сервера.
3. При любом изменении панель делает полный `awg-quick down` + `up`. Это короткий (~1 сек) разрыв всех пиров, но гарантирует, что параметры обфускации (Jc, S1–S4, H1–H4) реально применяются. `awg syncconf` для этого не годится — он **не обновляет** обфускацию на живом интерфейсе, из-за чего конфиг клиента расходится с сервером и handshake ломается.
4. На странице клиента — готовый конфиг, кнопка скачивания `.conf` и **QR-код** для приложения AmneziaWG на телефоне.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | учётка админа (создаётся при первом старте) | `admin` / `changeme` |
| `SECRET_KEY` | подпись cookie-сессий (обязательно сменить) | — |
| `PUBLIC_ENDPOINT` | публичный IP/хост для Endpoint в конфигах клиентов | автоопределение |
| `DEFAULT_DNS` | DNS по умолчанию для клиентов | `1.1.1.1, 1.0.0.1` |
| `WG_BIN` / `WG_QUICK_BIN` | бинарники (`awg`/`awg-quick` или `wg`/`wg-quick`) | `awg` / `awg-quick` |
| `APPLY_TO_SYSTEM` | `1` — применять к системе, `0` — dry-run (только БД/файлы) | `1` |

## Разработка (без AWG, на любой ОС)

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Dry-run, без обращения к системе:
APPLY_TO_SYSTEM=0 AWG_CONFIG_DIR=./_cfg DATABASE_URL=sqlite:///./dev.db \
  SECRET_KEY=dev uvicorn app.main:app --reload --port 8080
```

## Структура

```
app/
  main.py        FastAPI + middleware + lifecycle
  config.py      настройки из env
  database.py    SQLAlchemy
  models.py      Server / Peer / User
  crypto.py      генерация ключей X25519 (через cryptography, формат как у wg)
  awg.py         рендер конфигов, awg-quick/syncconf, выдача IP
  auth.py        логин, bcrypt, сессии
  crud.py        операции БД + применение к системе
  schemas.py     валидация форм
  qr.py          QR-код в data-URI
  routers/       auth, servers, peers
  templates/     Jinja2 + HTMX
  static/        style.css
```

## Безопасность — важное

- Не открывайте порт панели наружу. Только SSH-туннель.
- Смените `SECRET_KEY` и пароль.
- Приватные ключи серверов/клиентов хранятся в SQLite (`/data`) — защитите том.
```
