import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type MouseEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { Loading, Message } from "../../shared/components/Message";
import { Pagination } from "../../shared/components/Pagination";
import { NO_PROFILE_IMAGE, dash, round0 } from "../../shared/format";
import { useAsync } from "../../shared/hooks/useAsync";
import { compcardsApi } from "../compcards/api";
import { actorsApi } from "./api";
import {
  FILTER_KEYS, SORT_LABELS, STATUS_LABELS, pick, readListParams, toSearch,
  type ListKey, type ListParams,
} from "./listParams";
import type { Actor, AiParsed } from "./types";

export function ActorListPage() {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const p = readListParams(search);
  const queryKey = search.toString();

  const { data, error, loading } = useAsync(
    () => actorsApi.list(pick(p, ["q", "m", "ai_query", "gender", "height_group", "birth_group", "sort", "status_filter", "lesson_id", "page", "per_page"])),
    [queryKey]
  );

  const [selected, setSelected] = useState<number[]>([]);
  const [downloadError, setDownloadError] = useState("");
  useEffect(() => setSelected([]), [queryKey]);

  /** 조건을 바꾼 목록 주소. page를 따로 주지 않으면 1페이지로 돌아간다. */
  const hrefWith = (changes: Partial<ListParams>) => `/${toSearch({ ...p, page: "1", ...changes })}`;
  const go = (changes: Partial<ListParams>) => navigate(hrefWith(changes));

  const detailSearch = toSearch(p);
  const items = data?.items ?? [];

  async function downloadSelected() {
    setDownloadError("");
    if (selected.length === 0) {
      setDownloadError("다운로드할 배우를 먼저 선택해 주세요.");
      return;
    }
    try {
      await compcardsApi.downloadSelected(selected);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : "다운로드에 실패했습니다.");
    }
  }

  return (
    <>
      <div className="page-top">
        <div>
          <h1 className="page-title">소속 배우</h1>
          <div className="page-sub">Damactors 내부 전용 · 총 {data?.total_count ?? 0}명</div>
        </div>
        {hasRole("admin", "staff") && <Link className="btn primary" to="/actors/new">+ 배우 추가</Link>}
      </div>

      <div className="top-controls">
        <div className="controls-row controls-row-top">
          <div className="view-toggle-bar">
            <Link className={`view-toggle-btn ${p.view === "card" ? "active" : ""}`} to={hrefWith({ view: "card", page: p.page })}>
              카드형 보기
            </Link>
            <Link className={`view-toggle-btn ${p.view === "list" ? "active" : ""}`} to={hrefWith({ view: "list", page: p.page })}>
              리스트형 보기
            </Link>
          </div>
        </div>

        <div className="controls-row controls-row-bottom">
          <div className="selection-toolbar">
            <label className="select-all-wrap">
              <input
                type="checkbox"
                checked={items.length > 0 && selected.length === items.length}
                onChange={(e) => setSelected(e.target.checked ? items.map((a) => a.id) : [])}
              />
              <span>전체선택</span>
            </label>
            <span className="selected-count">선택됨: <strong>{selected.length}</strong>명</span>
            <button type="button" className="selection-btn" onClick={downloadSelected}>선택 PDF</button>
            <a className="mini-btn ghost" href={compcardsApi.mergedUrl(pick(p, FILTER_KEYS))}>통합 PDF</a>
          </div>

          <div className="right-tools">
            <FilterPopup params={p} isTeacher={user?.role === "teacher"} lessons={data?.teacher_lessons ?? []} onApply={go} />
            <SortDropdown sort={p.sort} hrefFor={(sort) => hrefWith({ sort })} />
            <div className="status-tabs">
              {[["", "전체"], ["active", "활동중"], ["expired", "계약만료"]].map(([value, label]) => (
                <Link key={value} className={`sort-tab ${p.status_filter === value ? "active" : ""}`} to={hrefWith({ status_filter: value })}>
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>

      <ActiveFilters params={p} removeHref={(key) => hrefWith({ [key]: "" })} clearAllHref={`/${toSearch({ view: p.view, per_page: p.per_page })}`} />

      <Message error={error || downloadError} />
      {loading && !data && <Loading />}

      {data && (
        <>
          {p.view === "card" ? (
            <div className="grid">
              {p.ai_query && <AiResultBox query={p.ai_query} parsed={data.ai_parsed} />}
              {items.map((actor) => (
                <ActorCard key={actor.id} actor={actor} href={`/actors/${actor.id}${detailSearch}`} selected={selected} setSelected={setSelected} items={items} />
              ))}
            </div>
          ) : (
            <div className="actor-list-wrap">
              {p.ai_query && <div style={{ marginBottom: 16 }}><AiResultBox query={p.ai_query} parsed={data.ai_parsed} /></div>}
              <ActorTable items={items} detailSearch={detailSearch} selected={selected} setSelected={setSelected} />
            </div>
          )}

          <Pagination page={data.page} totalPages={data.total_pages} hrefFor={(page) => hrefWith({ page: String(page) })} />
        </>
      )}
    </>
  );
}

// ---------- 선택 (Shift 클릭으로 범위 선택) ----------

type SelectionProps = {
  items: Actor[];
  selected: number[];
  setSelected: (ids: number[]) => void;
};

function useRangeSelect({ items, selected, setSelected }: SelectionProps) {
  const last = useRef<number | null>(null);

  return (actorId: number, checked: boolean, shiftKey: boolean) => {
    const ids = new Set(selected);
    const index = items.findIndex((a) => a.id === actorId);
    const lastIndex = last.current === null ? -1 : items.findIndex((a) => a.id === last.current);

    if (shiftKey && lastIndex >= 0) {
      const [from, to] = [index, lastIndex].sort((a, b) => a - b);
      for (const a of items.slice(from, to + 1)) {
        if (checked) ids.add(a.id);
        else ids.delete(a.id);
      }
    } else if (checked) {
      ids.add(actorId);
    } else {
      ids.delete(actorId);
    }

    last.current = actorId;
    setSelected(items.filter((a) => ids.has(a.id)).map((a) => a.id));
  };
}

// ---------- 카드형 ----------

function ActorCard({ actor, href, ...selection }: { actor: Actor; href: string } & SelectionProps) {
  const toggle = useRangeSelect(selection);
  const photo = actor.photo_thumb_path || actor.photo_path;

  return (
    <div className="card-select-wrap">
      <label className="actor-check" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={selection.selected.includes(actor.id)}
          onClick={(e: MouseEvent<HTMLInputElement>) => toggle(actor.id, e.currentTarget.checked, e.shiftKey)}
          readOnly
        />
      </label>

      <Link className="card" to={href}>
        <div className="card-img">
          <div className={`card-status-badge ${actor.contract_status ?? ""}`}>{actor.contract_status_label}</div>
          <img src={photo || NO_PROFILE_IMAGE} alt={photo ? actor.name : "사진 없음"} loading="lazy" decoding="async" />
        </div>

        <div className="card-body">
          <div className="card-name">
            {actor.name}
            {actor.manager_name && <span className="mgr"> · {actor.manager_name}</span>}
          </div>

          <div className="chips">
            <span className="chip">{dash(actor.gender)}</span>
            <span className="chip birth-chip">{dash(actor.birth_year)}년생</span>
            <span className="chip">{round0(actor.height_cm)}cm</span>
            <span className="chip">{round0(actor.weight_kg)}kg</span>
          </div>

          <div className="rows">
            <div className="row"><div className="k">학교</div><div className="v">{dash(actor.school)}</div></div>
            <div className="row"><div className="k">취미</div><div className="v">{dash(actor.hobby)}</div></div>
            <div className="row truncate"><div className="k">특기</div><div className="v">{dash(actor.specialty)}</div></div>
            <div className="row"><div className="k">시작</div><div className="v">{dash(actor.contract_date)}</div></div>
            <div className="row"><div className="k">만료</div><div className="v">{dash(actor.contract_end_date)}</div></div>
          </div>
        </div>
      </Link>
    </div>
  );
}

// ---------- 리스트형 ----------

function ActorTable({ items, detailSearch, ...selection }: { items: Actor[]; detailSearch: string } & Omit<SelectionProps, "items">) {
  const navigate = useNavigate();
  const toggle = useRangeSelect({ items, ...selection });

  return (
    <table className="actor-list-table">
      <thead>
        <tr>
          <th>선택</th><th>상태</th><th>사진</th><th>No.</th><th>이름</th><th>담당 매니저</th><th>성별</th>
          <th>년생</th><th>키</th><th>몸무게</th><th>학교</th><th>계약 시작일</th><th>계약 만료일</th><th>상세</th>
        </tr>
      </thead>
      <tbody>
        {items.map((actor) => {
          const href = `/actors/${actor.id}${detailSearch}`;
          const photo = actor.photo_thumb_path || actor.photo_path;
          return (
            <tr
              key={actor.id}
              onClick={(e) => {
                if (!(e.target as HTMLElement).closest("input, button, a")) navigate(href);
              }}
            >
              <td>
                <input
                  type="checkbox"
                  checked={selection.selected.includes(actor.id)}
                  onClick={(e: MouseEvent<HTMLInputElement>) => toggle(actor.id, e.currentTarget.checked, e.shiftKey)}
                  readOnly
                />
              </td>
              <td><span className={`list-status-badge ${actor.contract_status ?? ""}`}>{actor.contract_status_label}</span></td>
              <td><img src={photo || NO_PROFILE_IMAGE} className="list-thumb" alt={photo ? actor.name : "사진 없음"} loading="lazy" decoding="async" /></td>
              <td>{actor.id}</td>
              <td>{actor.name}</td>
              <td>{dash(actor.manager_name)}</td>
              <td>{dash(actor.gender)}</td>
              <td>{dash(actor.birth_year)}</td>
              <td>{round0(actor.height_cm)}</td>
              <td>{round0(actor.weight_kg)}</td>
              <td>{dash(actor.school)}</td>
              <td>{dash(actor.contract_date)}</td>
              <td>{dash(actor.contract_end_date)}</td>
              <td><Link className="list-detail-link" to={href}>보기</Link></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------- AI 검색 결과 설명 ----------

function AiResultBox({ query, parsed }: { query: string; parsed: AiParsed | null }) {
  return (
    <div className="ai-result-box">
      <div className="ai-result-title">AI 추천 검색 결과</div>
      <div className="ai-result-sub">"{query}" 기준으로 취미, 특기, 소개, 학교 정보를 분석해 관련 배우를 정렬했어요.</div>
      {parsed && (
        <div className="ai-tags">
          {parsed.gender && <span className="chip">성별 해석: {parsed.gender}</span>}
          {parsed.birth_group && <span className="chip">년대생 해석: {parsed.birth_group.slice(0, 2)}년대</span>}
          {parsed.height_group && <span className="chip">키 해석: {parsed.height_group}대</span>}
          {parsed.keywords.slice(0, 8).map((kw) => <span key={kw} className="chip">키워드: {kw}</span>)}
        </div>
      )}
    </div>
  );
}

// ---------- 필터 / 정렬 ----------

function usePopup<T extends HTMLElement>() {
  const [open, setOpen] = useState(false);
  const ref = useRef<T>(null);
  useEffect(() => {
    const close = (e: globalThis.MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);
  return { open, setOpen, ref };
}

type FilterProps = {
  params: ListParams;
  isTeacher: boolean;
  lessons: { id: number; lesson_name: string | null; lesson_days: string | null }[];
  onApply: (changes: Partial<ListParams>) => void;
};

function FilterPopup({ params, isTeacher, lessons, onApply }: FilterProps) {
  const { open, setOpen, ref } = usePopup<HTMLDivElement>();
  const [draft, setDraft] = useState(pick(params, ["gender", "height_group", "birth_group", "lesson_id"]));

  // URL 값이 바뀌면 입력 중인 값도 맞춘다
  useEffect(() => {
    setDraft(pick(params, ["gender", "height_group", "birth_group", "lesson_id"]));
  }, [params.gender, params.height_group, params.birth_group, params.lesson_id]);

  const select = (key: string) => (e: ChangeEvent<HTMLSelectElement>) => setDraft({ ...draft, [key]: e.target.value });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    onApply(draft);
    setOpen(false);
  }

  return (
    <div className="filter-wrap" ref={ref}>
      <button type="button" className="filter-open-btn" onClick={() => setOpen(!open)}>
        <span className="filter-ico">⚙</span>
        <span>필터</span>
      </button>

      <div className={`filter-popup ${open ? "show" : ""}`}>
        <form className="filter-popup-form" onSubmit={onSubmit}>
          <div className="filter-popup-title">필터 설정</div>
          <div className="filter-popup-grid">
            <div className="field">
              <label>성별</label>
              <select value={draft.gender} onChange={select("gender")}>
                <option value="">전체</option>
                <option value="남자">남자</option>
                <option value="여자">여자</option>
              </select>
            </div>
            <div className="field">
              <label>키</label>
              <select value={draft.height_group} onChange={select("height_group")}>
                <option value="">전체</option>
                {["150", "160", "170", "180"].map((h) => <option key={h} value={h}>{h}대</option>)}
              </select>
            </div>
            <div className="field">
              <label>년대생</label>
              <select value={draft.birth_group} onChange={select("birth_group")}>
                <option value="">전체</option>
                {["1980", "1990", "2000", "2010"].map((b) => <option key={b} value={b}>{b.slice(2)}년대생</option>)}
              </select>
            </div>
          </div>

          {isTeacher && (
            <div className="field">
              <label>수업</label>
              <select value={draft.lesson_id} onChange={select("lesson_id")}>
                <option value="">전체 수업</option>
                {lessons.map((l) => (
                  <option key={l.id} value={String(l.id)}>
                    {l.lesson_name}{l.lesson_days ? ` · ${l.lesson_days}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="filter-popup-actions">
            <button className="mini-btn primary" type="submit">적용</button>
            <button className="mini-btn ghost" type="button" onClick={() => { onApply({ gender: "", height_group: "", birth_group: "", lesson_id: "" }); setOpen(false); }}>
              초기화
            </button>
            <button className="mini-btn ghost" type="button" onClick={() => setOpen(false)}>닫기</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function SortDropdown({ sort, hrefFor }: { sort: string; hrefFor: (sort: string) => string }) {
  const { open, setOpen, ref } = usePopup<HTMLDivElement>();
  return (
    <div className={`sort-dropdown ${open ? "open" : ""}`} ref={ref}>
      <button type="button" className="sort-dropdown-btn" onClick={() => setOpen(!open)}>
        정렬: <span className="sort-current">{SORT_LABELS[sort] ?? "기본순"}</span>
        <span className="sort-caret">▼</span>
      </button>
      <div className="sort-dropdown-menu">
        {Object.entries(SORT_LABELS).map(([value, label]) => (
          <Link key={value} className={`sort-dropdown-item ${sort === value ? "active" : ""}`} to={hrefFor(value)} onClick={() => setOpen(false)}>
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

// ---------- 적용된 필터 칩 ----------

function ActiveFilters({ params, removeHref, clearAllHref }: { params: ListParams; removeHref: (key: ListKey) => string; clearAllHref: string }) {
  const chips: [ListKey, string][] = [];
  if (params.q) chips.push(["q", `이름: ${params.q}`]);
  if (params.m) chips.push(["m", `매니저: ${params.m}`]);
  if (params.ai_query) chips.push(["ai_query", `AI검색: ${params.ai_query}`]);
  if (params.gender) chips.push(["gender", `성별: ${params.gender}`]);
  if (params.height_group) chips.push(["height_group", `키: ${params.height_group}대`]);
  if (params.birth_group) chips.push(["birth_group", `년대생: ${params.birth_group.slice(0, 2)}년대`]);
  if (params.sort) chips.push(["sort", `정렬: ${SORT_LABELS[params.sort] ?? "기본순"}`]);
  if (params.status_filter) chips.push(["status_filter", `상태: ${STATUS_LABELS[params.status_filter] ?? params.status_filter}`]);

  if (chips.length === 0) return null;

  return (
    <div className="active-filters">
      <div className="active-filters-label">적용된 필터</div>
      <div className="active-filter-chips">
        {chips.map(([key, label]) => (
          <Link key={key} className={`filter-chip removable ${key === "ai_query" ? "ai-chip" : ""}`} to={removeHref(key)}>
            <span className="filter-chip-text">{label}</span>
            <span className="filter-chip-remove">×</span>
          </Link>
        ))}
      </div>
      <Link className="clear-all-filters" to={clearAllHref}>전체 해제</Link>
    </div>
  );
}
