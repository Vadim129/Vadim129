# Деплой на Cloudflare (Containers)

Архитектура: **Cloudflare Worker** (`cloudflare/src/index.ts`) держит
**контейнер** с обычным Docker-образом бота (`./Dockerfile`, Python + ffmpeg +
rembg). Бот как и раньше ходит в Telegram поллингом сам; Worker нужен только
чтобы контейнер жил, не спал (cron-пинг каждые 5 минут) и отвечал healthcheck.

```
Telegram ⇄ (поллинг, наружу) контейнер с ботом ⇄ health :8080 ⇄ Worker ⇄ ты открываешь ссылку
```

> ⚠️ Containers доступны только на тарифе **Workers Paid** ($5/мес). На
> бесплатном Cloudflare деплой упадёт на шаге контейнера — тогда используй
> GitHub Actions (`.github/workflows/deepstick-bot.yml`) или Docker на VPS.

## Что куда вставлять (все секреты — в GitHub, мне в чат ключи слать не надо)

Открой страницу секретов репозитория:
**https://github.com/Vadim129/Vadim129/settings/secrets/actions**
(кнопка **New repository secret**) и добавь три секрета:

| Имя секрета | Где взять значение |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather (тот, что уже есть) |
| `CLOUDFLARE_API_TOKEN` | https://dash.cloudflare.com/profile/api-tokens → **Create Token** → шаблон **Edit Cloudflare Workers** (если в списке прав есть **Workers Containers — Edit**, добавь и его) → создать → скопировать один раз показанный токен |
| `CLOUDFLARE_ACCOUNT_ID` | https://dash.cloudflare.com → **Workers & Pages** — справа/в адресе страницы указан **Account ID** (32 hex-символа) |

После этого напиши ассистенту «готово» — деплой запустится из GitHub Actions
(workflow `Deploy DeepStick to Cloudflare`), в конце он сам разбудит контейнер
и даст ссылку вида:

```
https://deepstick-bot.<твой-subdomain>.workers.dev/health
{"ok": true, "service": "deepstick-bot"}
```

Эта ссылка — только healthcheck («бот жив»), сам бот общается в Telegram.

## Деплой руками (альтернатива, со своего компьютера)

Нужны Node.js 22+, Docker и тариф Workers Paid:

```bash
cd deepstick-bot
npm install
npx wrangler login
npx wrangler secret put BOT_TOKEN     # вставить токен от BotFather
npx wrangler deploy                   # соберёт Docker-образ и задеплоит всё
curl https://deepstick-bot.<subdomain>.workers.dev/health
npx wrangler tail                     # живые логи воркера/контейнера
```

## Как это работает внутри

- `wrangler.jsonc` — контейнер `standard-1` (0.5 vCPU / 4 GiB; rembg+ffmpeg
  меньше не хватит), `max_instances: 1` (два поллинга одного бота нельзя).
- Секреты воркера (`BOT_TOKEN`, опционально `ADMIN_IDS`, `AI_PROVIDER`)
  воркер прокидывает в контейнер переменными окружения при старте.
- `sleepAfter: 10m` + cron `*/5 * * * *` в воркере = контейнер не засыпает.
- В боте при заданном `PORT` рядом с поллингом живёт health-сервер, а поллинг
  обёрнут в супервизор: Telegram моргнул — бот переподключится, а не умрёт.
- Файловая система контейнера эфемерна: при рестарте контейнера локальная
  история/настройки (SQLite в `/app/data`) сбросятся. Сам стикерпак хранится
  в Telegram и не теряется.

## Остановить

Cloudflare Dashboard → **Workers & Pages** → `deepstick-bot` → **Delete**
(или отключи триггер в GitHub Actions, если деплоил через него).
