import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  BOT_CONTAINER: DurableObjectNamespace<BotContainer>;
  // Секреты воркера (wrangler secret put ...): прокидываются в контейнер при старте
  BOT_TOKEN?: string;
  ADMIN_IDS?: string;
  AI_PROVIDER?: string;
}

/**
 * Контейнер с Python-ботом (см. ../../Dockerfile).
 * Бот работает поллингом Telegram — HTTP ему нужен только как healthcheck,
 * чтобы Cloudflare держал контейнер живым и мог проверять готовность.
 */
export class BotContainer extends Container<Env> {
  defaultPort = 8080;
  // Cron ниже пингует каждые 5 минут — при sleepAfter 10m контейнер не уснёт.
  sleepAfter = "10m";
  enableInternet = true; // api.telegram.org нужен наружу

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  constructor(ctx: DurableObjectState<any>, env: Env) {
    super(ctx, env);
    this.envVars = {
      BOT_TOKEN: env.BOT_TOKEN ?? "",
      ADMIN_IDS: env.ADMIN_IDS ?? "",
      AI_PROVIDER: env.AI_PROVIDER ?? "none",
      REMOVE_BG: "auto",
      DATA_DIR: "/app/data",
      PORT: "8080",
    };
  }

  override onStart() {
    console.log("DeepStick container started");
  }

  override onStop() {
    console.log("DeepStick container stopped");
  }

  override onError(error: unknown) {
    console.log("DeepStick container error:", error);
  }
}

async function ping(env: Env): Promise<Response> {
  const container = getContainer(env.BOT_CONTAINER, "main");
  return container.fetch(new Request("http://container/health"));
}

export default {
  // Открыть ссылку воркера = проверить/разбудить бота
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health") {
      try {
        const res = await ping(env);
        const body = await res.text();
        return new Response(
          `DeepStick bot container: ${res.status}\n${body}\n\n` +
            `Бот работает в Telegram (поллинг). Эта страница — только healthcheck.`,
          { status: res.ok ? 200 : 502, headers: { "content-type": "text/plain; charset=utf-8" } },
        );
      } catch (e) {
        return new Response(`Container is starting or unavailable: ${e}`, { status: 503 });
      }
    }
    return new Response("Not found", { status: 404 });
  },

  // Держим контейнер awake: пинг каждые 5 минут (см. triggers в wrangler.jsonc)
  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(
      ping(env)
        .then((r) => console.log("keep-alive ping:", r.status))
        .catch((e) => console.log("keep-alive ping failed:", e)),
    );
  },
} satisfies ExportedHandler<Env>;
