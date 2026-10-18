/**
 * 프론트엔드 E2E 스모크 테스트. 실제 브라우저(헤드리스 Chromium)로 역할별 주요 흐름을 따라간다.
 *
 * 준비 (데이터가 생기므로 반드시 빈 임시 DB로 실행한다):
 *   1) 백엔드:  cd backend && STORAGE_DIR=/tmp/actor-e2e SECRET_KEY=e2e .venv/bin/uvicorn app.main:app --port 8000
 *   2) 프론트:  cd frontend && npm run dev
 *   3) 최초 1회: npx playwright install chromium
 * 실행:
 *   npm run e2e            (BASE=http://localhost:5173 기본값)
 * 실패하면 e2e/shots/에 스크린샷이 남는다.
 */
import { chromium } from "playwright";
import fs from "node:fs";
import zlib from "node:zlib";

const BASE = process.env.BASE ?? "http://localhost:5173";
const SHOTS = new URL("./shots/", import.meta.url).pathname;
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const consoleErrors = [];
let step = "";
let currentPage = null;

function ok(name) { results.push(["OK", name]); console.log("OK  ", name); }
async function check(name, fn) {
  step = name;
  try { await fn(); ok(name); }
  catch (e) {
    results.push(["FAIL", name, e.message.split("\n")[0]]);
    console.log("FAIL", name, "→", e.message.split("\n")[0]);
    for (const [label, pg] of pages) {
      await pg.screenshot({ path: SHOTS + `fail-${results.length}-${label}.png`, fullPage: true }).catch(() => {});
      console.log("     ", label, "URL:", pg.url());
    }
  }
}

// 작은 PNG (1x1 빨강) — 사진 업로드용
function pngBytes() {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32 ? zlib.crc32(td) >>> 0 : 0);
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(1, 0); ihdr.writeUInt32BE(1, 4); ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.from([0, 255, 0, 0]);
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

const browser = await chromium.launch();
const pages = [];

async function newPage(label) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.accept());
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(`[${step}] ${m.text()}`); });
  page.on("pageerror", (e) => consoleErrors.push(`[${step}] pageerror: ${e.message}`));
  pages.push([label, page]);
  return page;
}

const field = (page, label) => page.locator(".field", { has: page.locator(`label:text-is("${label}")`) }).locator("input, select, textarea").first();

async function login(page, username, password) {
  await page.goto(`${BASE}/login`);
  await field(page, "아이디").fill(username);
  await field(page, "비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.waitForURL(`${BASE}/`);
  await page.getByText(`(${username === "admin" ? "admin" : ""}`).first().waitFor({ timeout: 3000 }).catch(() => {});
}

const admin = await newPage("admin");

await check("비로그인: 목록 화면과 보기 전용 표시", async () => {
  await admin.goto(BASE);
  await admin.getByText("소속 배우").waitFor();
  await admin.getByText("보기 전용").waitFor();
});

await check("비로그인: 로그인 필요 화면 → 로그인 화면으로 이동", async () => {
  await admin.goto(`${BASE}/attendance`);
  await admin.waitForURL(/\/login\?next=/);
});

await check("로그인 실패 메시지", async () => {
  await field(admin, "아이디").fill("admin");
  await field(admin, "비밀번호").fill("wrong");
  await admin.getByRole("button", { name: "로그인" }).click();
  await admin.getByText("아이디 또는 비밀번호가 올바르지 않습니다.").waitFor();
});

await check("admin 로그인 후 원래 가려던 화면(next)으로 이동", async () => {
  await field(admin, "비밀번호").fill("1234");
  await admin.getByRole("button", { name: "로그인" }).click();
  await admin.waitForURL(`${BASE}/attendance`);
  await admin.getByText("최고관리자 (admin)").waitFor();
});

await check("계정 생성 (staff, teacher)", async () => {
  await admin.goto(`${BASE}/admin/users`);
  for (const [name, username, role] of [["E2E스태프", "staffe2e", "staff"], ["E2E선생", "teache2e", "teacher"]]) {
    await field(admin, "이름").fill(name);
    await field(admin, "아이디").fill(username);
    await field(admin, "비밀번호").fill("pass1234");
    await field(admin, "비밀번호 확인").fill("pass1234");
    await field(admin, "권한").selectOption(role);
    await admin.getByRole("button", { name: "계정 생성" }).click();
    await admin.getByText("계정이 생성되었습니다.").waitFor();
    await admin.locator("td", { hasText: username }).waitFor();
  }
  await admin.screenshot({ path: SHOTS + "admin-accounts.png", fullPage: true });
});

await check("중복 아이디 에러 메시지", async () => {
  await field(admin, "이름").fill("x");
  await field(admin, "아이디").fill("staffe2e");
  await field(admin, "비밀번호").fill("pass1234");
  await field(admin, "비밀번호 확인").fill("pass1234");
  await admin.getByRole("button", { name: "계정 생성" }).click();
  await admin.getByText("이미 사용 중인 아이디입니다.").waitFor();
});

await check("배우 등록 (사진, 계약일 → 만료일 자동 계산)", async () => {
  await admin.goto(`${BASE}/`);
  await admin.getByRole("link", { name: "+ 배우 추가" }).click();
  await admin.waitForURL(`${BASE}/actors/new`);
  await field(admin, "이름 *").fill("E2E배우");
  await field(admin, "성별").selectOption("여자");
  await field(admin, "년생").fill("1995");
  await field(admin, "키(cm)").fill("168");
  await field(admin, "취미").fill("승마, 요가");
  await field(admin, "전화번호 뒤 4자리").pressSequentially("98-76");
  await field(admin, "계약 시작일").pressSequentially("20240301");
  const end = await field(admin, "계약 만료일").inputValue();
  if (end !== "2025-02-28") throw new Error(`만료일 자동 계산 ${end}`);
  if ((await field(admin, "전화번호 뒤 4자리").inputValue()) !== "9876") throw new Error("전화번호 숫자만");
  await admin.locator(".u", { hasText: "프로필 사진" }).locator("input[type=file]").setInputFiles({ name: "p.png", mimeType: "image/png", buffer: pngBytes() });
  await admin.getByRole("button", { name: "저장" }).click();
  await admin.waitForURL(/\/actors\/\d+$/);
  await admin.locator(".detail-profile-name", { hasText: "E2E배우" }).waitFor();
  await admin.getByText("2025-02-28").first().waitFor();
  const src = await admin.locator(".detail-photo img").getAttribute("src");
  if (!src.startsWith("/media/uploads/")) throw new Error(`사진 경로 ${src}`);
  await admin.screenshot({ path: SHOTS + "actor-detail.png", fullPage: true });
});

const actorUrl = admin.url();
const actorId = actorUrl.split("/").pop();

await check("수업일지 추가/수정 (상세 → 탭 → 폼)", async () => {
  await admin.getByRole("link", { name: "트레이닝 피드백" }).click();
  await admin.getByRole("link", { name: "+ 추가" }).click();
  await field(admin, "날짜").fill("2024-05-01");
  await field(admin, "내용").fill("발성 연습");
  await admin.getByRole("button", { name: "추가" }).click();
  await admin.waitForURL(/tab=classlog/);
  await admin.getByText("발성 연습").waitFor();
  await admin.getByRole("link", { name: "수정", exact: true }).first().click();
  await field(admin, "내용").fill("발성 연습 (수정)");
  await admin.getByRole("button", { name: "저장" }).click();
  await admin.getByText("발성 연습 (수정)").waitFor();
});

await check("캐스팅 미팅 기록 추가 (여러 줄 입력)", async () => {
  await admin.goto(`${actorUrl}?tab=casting_meetings`);
  await admin.getByRole("link", { name: "+ 추가" }).click();
  await field(admin, "날짜").fill("2024-06-01");
  await field(admin, "내용").fill("미팅 메모");
  await admin.getByRole("button", { name: "추가" }).click();
  await admin.getByText("미팅 메모").waitFor();
});

await check("선생님 수업 추가와 배우 배정", async () => {
  await admin.goto(`${BASE}/admin/users`);
  await admin.getByRole("button", { name: "선생님 관리" }).click();
  const card = admin; // teacher 계정이 하나뿐이라 화면 전체에서 찾는다
  await card.getByRole("button", { name: "수업 관리 열기" }).click();
  await card.getByPlaceholder("예: 카메라연기").fill("E2E연기반");
  await card.getByPlaceholder("예: 화/목").fill("월,화,수,목,금,토,일");
  await card.getByRole("button", { name: "수업 추가" }).click();
  await admin.getByText("E2E연기반").waitFor();
  await card.getByPlaceholder("이 수업 배우 검색...").fill("E2E");
  await card.getByLabel("E2E배우").check();
  await card.getByRole("button", { name: "이 수업 배우 저장" }).click();
  await card.getByText("전체 배정 배우 1명").waitFor();
  await admin.screenshot({ path: SHOTS + "admin-teachers.png", fullPage: true });
});

await check("목록: 필터(성별), AI 검색, 리스트형 보기", async () => {
  await admin.goto(`${BASE}/`);
  await admin.getByRole("button", { name: /필터/ }).click();
  await admin.locator(".filter-popup").locator(".field", { hasText: "성별" }).locator("select").selectOption("남자");
  await admin.getByRole("button", { name: "적용" }).click();
  await admin.waitForURL(/gender=/);
  await admin.waitForLoadState("networkidle");
  if (await admin.locator(".card-name", { hasText: "E2E배우" }).count()) throw new Error("남자 필터에 여자 배우가 보임");
  await admin.getByRole("link", { name: /성별: 남자/ }).click();
  await admin.waitForLoadState("networkidle");
  await admin.locator(".card-name", { hasText: "E2E배우" }).waitFor();

  await admin.getByPlaceholder("AI 검색 예: 헬스하는 남자 리스트").fill("승마하는 여자");
  await admin.getByRole("button", { name: "검색" }).click();
  await admin.getByText("AI 추천 검색 결과").waitFor();
  await admin.locator(".card-name", { hasText: "E2E배우" }).waitFor();
  await admin.getByRole("link", { name: "리스트형 보기" }).click();
  await admin.locator(".actor-list-table td", { hasText: "E2E배우" }).waitFor();
  await admin.screenshot({ path: SHOTS + "list-ai.png", fullPage: true });
});

await check("배우정보 수정 후 상세로 복귀 (검색 조건 유지)", async () => {
  await admin.goto(`${BASE}/?q=E2E`);
  await admin.locator(".card", { hasText: "E2E배우" }).click();
  await admin.getByRole("link", { name: "배우정보 수정" }).click();
  await field(admin, "학교").fill("한예종");
  await admin.getByRole("button", { name: "저장" }).click();
  await admin.waitForURL(/\/actors\/\d+\?q=E2E/);
  await admin.getByText("한예종").waitFor();
  if ((await admin.locator(".detail-profile-chip", { hasText: "성별" }).innerText()).indexOf("여자") < 0) throw new Error("성별이 유지되지 않음");
  await admin.getByRole("link", { name: "← 목록으로" }).click();
  await admin.waitForURL(`${BASE}/?q=E2E`);
});

await check("출결: 번호 자동판별 + 피드백 저장 → 수업일지 기록", async () => {
  await admin.goto(`${BASE}/attendance`);
  await field(admin, "수업 선택").selectOption({ label: /E2E연기반/ }).catch(async () => {
    const opt = await admin.locator("option", { hasText: "E2E연기반" }).getAttribute("value");
    await field(admin, "수업 선택").selectOption(opt);
  });
  await admin.waitForLoadState("networkidle");
  const row = admin.locator("tr", { hasText: "E2E배우" });
  await row.getByPlaceholder("1234").fill("9876");
  await row.getByPlaceholder(/발성 좋음/).fill("집중도 좋음");
  await admin.getByRole("button", { name: "출결 저장" }).click();
  await admin.getByText("출결이 저장되었습니다.").waitFor();
  await admin.waitForLoadState("networkidle");
  if ((await row.getByPlaceholder("1234").inputValue()) !== "9876") throw new Error("저장 후 입력 번호가 비어 있음");
  if ((await row.locator("select").inputValue()) !== "출석") throw new Error("자동 출석 처리 안 됨");
  await admin.screenshot({ path: SHOTS + "attendance.png", fullPage: true });
  await admin.goto(`${actorUrl}?tab=classlog`);
  await admin.getByText("[E2E연기반] 집중도 좋음").waitFor();
});

const teacher = await newPage("teacher");

await check("teacher: 담당 배우만 보이고, 상세는 트레이닝 피드백 탭만", async () => {
  await login(teacher, "teache2e", "pass1234");
  await teacher.locator(".card-name", { hasText: "E2E배우" }).waitFor();
  const names = await teacher.locator(".card-name").allInnerTexts();
  if (names.length !== 1) throw new Error(`보이는 배우 ${names.length}명`);
  await teacher.locator(".card", { hasText: "E2E배우" }).click();
  await teacher.locator(".tab-btn").first().waitFor();
  const tabs = await teacher.locator(".tab-btn").allInnerTexts();
  if (tabs.join() !== "트레이닝 피드백") throw new Error(`탭: ${tabs}`);
  await teacher.getByText("[E2E연기반] 집중도 좋음").waitFor();
  if (await teacher.getByRole("link", { name: "배우정보 수정" }).count()) throw new Error("teacher에게 수정 버튼");
  if (await teacher.getByRole("button", { name: "삭제" }).count()) throw new Error("teacher에게 삭제 버튼");
});

await check("teacher: 관리자 화면 접근 불가", async () => {
  await teacher.goto(`${BASE}/admin/users`);
  await teacher.getByText("이 화면을 볼 권한이 없습니다.").waitFor();
});

await check("teacher: 비밀번호 변경", async () => {
  await teacher.goto(`${BASE}/account/password`);
  await field(teacher, "현재 비밀번호").fill("pass1234");
  await field(teacher, "새 비밀번호").fill("pass5678");
  await field(teacher, "새 비밀번호 확인").fill("pass5678");
  await teacher.getByRole("button", { name: "비밀번호 저장" }).click();
  await teacher.getByText("비밀번호가 변경되었습니다.").waitFor();
});

await check("로그아웃", async () => {
  await teacher.getByRole("button", { name: "로그아웃" }).click();
  await teacher.getByText("보기 전용").waitFor();
});

await check("키오스크: 번호 입력 → 출석, 다른 화면 이동 차단, 종료", async () => {
  await admin.goto(`${BASE}/attendance/kiosk`);
  await admin.getByText("출결번호를 입력해주세요.").waitFor();
  for (const d of "9876") await admin.locator(".kiosk-key", { hasText: new RegExp(`^${d}$`) }).click();
  await admin.getByText(/E2E배우 (출석 완료|이미 출석 처리되었습니다.)/).waitFor();
  await admin.screenshot({ path: SHOTS + "kiosk.png", fullPage: true });
  await admin.goto(`${BASE}/admin/users`);
  await admin.waitForURL(`${BASE}/attendance/kiosk`, { timeout: 5000 });
  await admin.getByRole("button", { name: "종료" }).click();
  await admin.waitForURL(`${BASE}/attendance`);
});

await check("배우 삭제 (admin)", async () => {
  await admin.goto(actorUrl);
  await admin.getByRole("button", { name: "배우 삭제" }).click();
  await admin.waitForURL(`${BASE}/`);
  await admin.goto(actorUrl);
  await admin.getByText("배우를 찾을 수 없습니다.").waitFor();
});

await browser.close();

console.log("\n=== 결과 ===");
const failed = results.filter((r) => r[0] === "FAIL");
console.log(`${results.length - failed.length}/${results.length} 통과`);
for (const f of failed) console.log("FAIL", f[1], "→", f[2]);
console.log("\n=== 브라우저 콘솔 에러 ===");
console.log(consoleErrors.length ? consoleErrors.join("\n") : "(없음)");
process.exit(failed.length ? 1 : 0);
