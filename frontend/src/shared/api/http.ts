/**
 * 백엔드 API 호출 래퍼.
 * - 세션 쿠키를 함께 보낸다 (같은 origin이라 CORS 없음)
 * - 실패하면 ApiError를 던진다. detail은 화면에 그대로 보여줄 수 있는 한국어 메시지다.
 * - 401(로그인 필요)이면 로그인 화면으로, KIOSK_MODE면 키오스크 화면으로 보낸다.
 */
export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Query = Record<string, string | number | undefined | null>;

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  /** 401이어도 로그인 화면으로 보내지 않는다 (로그인 상태 확인용) */
  allowAnonymous?: boolean;
};

export function toQueryString(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

function errorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return "입력값을 확인해주세요.";
  }
  return fallback;
}

function handleGlobalError(err: ApiError, options: Options) {
  const here = window.location.pathname + window.location.search;
  if (err.code === "KIOSK_MODE" && window.location.pathname !== "/attendance/kiosk") {
    window.location.assign("/attendance/kiosk");
  } else if (err.status === 401 && !options.allowAnonymous && window.location.pathname !== "/login") {
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
  }
}

async function request(path: string, options: Options): Promise<Response> {
  const init: RequestInit = { method: options.method ?? "GET", credentials: "include", headers: {} };

  if (options.body instanceof FormData) {
    init.body = options.body;
  } else if (options.body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const res = await fetch(path + toQueryString(options.query), init);
  if (!res.ok) {
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await res.json().catch(() => null) : null;
    const err = new ApiError(res.status, errorMessage(data, `요청에 실패했습니다. (${res.status})`), data?.code);
    handleGlobalError(err, options);
    throw err;
  }
  return res;
}

export async function api<T = void>(path: string, options: Options = {}): Promise<T> {
  const res = await request(path, options);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** 파일 응답(PDF 등)을 받아서 브라우저 다운로드로 저장한다. */
export async function downloadFile(path: string, options: Options, fallbackName: string) {
  const res = await request(path, options);
  const blob = await res.blob();

  const disposition = res.headers.get("content-disposition") ?? "";
  const utf8Name = /filename\*=utf-8''([^;]+)/i.exec(disposition)?.[1];
  const plainName = /filename="?([^";]+)"?/i.exec(disposition)?.[1];
  const filename = utf8Name ? decodeURIComponent(utf8Name) : plainName ?? fallbackName;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
