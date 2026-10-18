import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { Loading, Message } from "../../shared/components/Message";
import { NO_PROFILE_IMAGE, dash, round0 } from "../../shared/format";
import { useAsync } from "../../shared/hooks/useAsync";
import { RecordPanel } from "../actor_records/RecordPanel";
import { recordTypeByTab } from "../actor_records/recordTypes";
import { actorsApi, fieldsFromActor } from "./api";
import { readListParams, toSearch } from "./listParams";
import type { Actor, ActorFiles } from "./types";

const TABS: { tab: string; label: string }[] = [
  { tab: "compcard", label: "컴카드" },
  { tab: "classlog", label: "트레이닝 피드백" },
  { tab: "auditions", label: "오디션" },
  { tab: "video", label: "연기영상" },
  { tab: "first_meeting", label: "방향성 및 특이사항" },
  { tab: "casting_management", label: "캐스팅관리" },
  { tab: "casting_meetings", label: "캐스팅 미팅" },
];

export function ActorDetailPage() {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const actorId = Number(useParams().actorId);
  const [search] = useSearchParams();

  // 목록 검색 조건은 그대로 들고 다닌다 (목록으로 돌아갈 때 복원)
  const listSearch = toSearch(readListParams(search));
  const isTeacher = user?.role === "teacher";
  const tab = isTeacher ? "classlog" : search.get("tab") || "compcard";
  const tabHref = (t: string) => {
    const params = new URLSearchParams(listSearch);
    params.set("tab", t);
    return `/actors/${actorId}?${params.toString()}`;
  };

  const { data: actor, error, reload } = useAsync(() => actorsApi.get(actorId), [actorId]);
  const [actionError, setActionError] = useState("");

  async function onDelete() {
    if (!window.confirm("정말 삭제할까요? 삭제 후 복구가 어렵습니다.")) return;
    try {
      await actorsApi.remove(actorId);
      navigate(`/${listSearch}`);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "삭제하지 못했습니다.");
    }
  }

  if (error) return <Message error={error} />;
  if (!actor) return <Loading />;

  const canEdit = hasRole("admin", "staff");
  const recordType = recordTypeByTab(tab);

  return (
    <>
      <div className="detail-top">
        <Link className="back" to={`/${listSearch}`}>← 목록으로</Link>
        <div className="actions">
          {canEdit && <Link className="btn" to={`/actors/${actorId}/edit${listSearch}`}>배우정보 수정</Link>}
          {hasRole("admin") && <button className="btn danger" type="button" onClick={onDelete}>배우 삭제</button>}
        </div>
      </div>

      <Message error={actionError} />

      <div className="detail">
        <div className="detail-left">
          <div className="detail-photo">
            <img src={actor.photo_path || NO_PROFILE_IMAGE} alt={actor.photo_path ? actor.name : "사진 없음"} loading="eager" decoding="async" />
          </div>

          {canEdit && (
            <QuickUpload
              actor={actor}
              className="upload-card"
              title="프로필 사진 빠른 업로드"
              accept="image/*"
              buttonLabel="업로드"
              hint="jpg/png/webp 권장"
              toFiles={(files) => ({ photo: files[0] })}
              onDone={reload}
            />
          )}

          <ProfileCard actor={actor} />
        </div>

        <div className="detail-right">
          <div className="tabs">
            {(isTeacher ? TABS.filter((t) => t.tab === "classlog") : TABS).map((t) => (
              <Link key={t.tab} className={`tab-btn ${tab === t.tab ? "active" : ""}`} to={tabHref(t.tab)}>
                {t.label}
              </Link>
            ))}
          </div>

          {tab === "compcard" && <CompcardPanel actor={actor} canEdit={canEdit} onChanged={reload} />}
          {tab === "video" && <VideoPanel actor={actor} canEdit={canEdit} />}
          {recordType && <RecordPanel actorId={actorId} type={recordType} />}
          {!recordType && !["compcard", "video"].includes(tab) && <p className="muted">알 수 없는 탭입니다.</p>}
        </div>
      </div>
    </>
  );
}

// ---------- 프로필 ----------

function ProfileCard({ actor }: { actor: Actor }) {
  return (
    <div className="detail-card detail-profile-card">
      <div className="detail-profile-head">
        <div className="detail-profile-title-wrap">
          <div className="detail-profile-overline">DAMACTORS ENT · ACTOR PROFILE</div>
          <div className="detail-profile-name-row">
            <h1 className="detail-profile-name">{actor.name}</h1>
            <span className={`detail-profile-status ${actor.contract_status ?? ""}`}>{actor.contract_status_label}</span>
          </div>
          <div className="detail-profile-manager">
            <span>담당 매니저 · {actor.manager_name || "미지정"}</span>
            <span>담당 선생님 · {actor.teacher_user_name || "미지정"}</span>
          </div>
        </div>
      </div>

      <div className="detail-profile-chips">
        <div className="detail-profile-chip"><span className="label">성별</span><strong>{dash(actor.gender)}</strong></div>
        <div className="detail-profile-chip"><span className="label">년생</span><strong>{dash(actor.birth_year)}{actor.birth_year ? "년생" : ""}</strong></div>
        <div className="detail-profile-chip"><span className="label">키</span><strong>{round0(actor.height_cm)}{actor.height_cm ? "cm" : ""}</strong></div>
        <div className="detail-profile-chip"><span className="label">몸무게</span><strong>{round0(actor.weight_kg)}{actor.weight_kg ? "kg" : ""}</strong></div>
      </div>

      <div className="detail-profile-grid">
        <div className="detail-profile-info-card"><div className="k">학교</div><div className="v">{dash(actor.school)}</div></div>
        <div className="detail-profile-info-card"><div className="k">취미</div><div className="v">{dash(actor.hobby)}</div></div>
        <div className="detail-profile-info-card detail-profile-info-card-wide"><div className="k">특기</div><div className="v">{dash(actor.specialty)}</div></div>
        <div className="detail-profile-info-card"><div className="k">계약 시작</div><div className="v">{dash(actor.contract_date)}</div></div>
        <div className="detail-profile-info-card"><div className="k">계약 만료</div><div className="v">{dash(actor.contract_end_date)}</div></div>
      </div>

      <div className="detail-profile-memo">
        <div className="detail-profile-memo-title">메모</div>
        {actor.bio ? <p className="detail-profile-memo-text">{actor.bio}</p> : <p className="muted">내용 없음</p>}
      </div>
    </div>
  );
}

// ---------- 빠른 업로드 (나머지 정보는 그대로 두고 파일만 바꾼다) ----------

type QuickUploadProps = {
  actor: Actor;
  className: string;
  title?: string;
  accept: string;
  multiple?: boolean;
  buttonLabel: string;
  hint: string;
  toFiles: (files: File[]) => ActorFiles;
  onDone: () => void;
};

function QuickUpload({ actor, className, title, accept, multiple, buttonLabel, hint, toFiles, onDone }: QuickUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (files.length === 0) return;
    setBusy(true);
    setError("");
    try {
      await actorsApi.update(actor.id, fieldsFromActor(actor), toFiles(files));
      setFiles([]);
      e.currentTarget.reset();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={className} onSubmit={onSubmit}>
      {title && <div className="upload-title">{title}</div>}
      <div className="upload-row">
        <input className="file" type="file" accept={accept} multiple={multiple} required onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        <button className="btn primary" type="submit" disabled={busy}>{busy ? "업로드 중..." : buttonLabel}</button>
      </div>
      <div className="upload-hint">{hint}</div>
      {error && <div className="upload-hint" style={{ color: "#c62828" }}>{error}</div>}
    </form>
  );
}

// ---------- 컴카드 ----------

function CompcardPanel({ actor, canEdit, onChanged }: { actor: Actor; canEdit: boolean; onChanged: () => void }) {
  const path = actor.compcard_path;
  return (
    <div className="panel-card">
      <div className="tab-top">
        <div className="panel-title">컴카드 미리보기</div>
      </div>

      {path ? (
        <>
          <div className="preview">
            {path.toLowerCase().endsWith(".pdf") ? (
              <iframe className="pdf" src={`${path}#toolbar=1&navpanes=0&view=FitH`} title="컴카드" />
            ) : (
              <img className="preview-img" src={actor.compcard_preview_path || path} alt="컴카드 미리보기" />
            )}
          </div>
          <div style={{ marginTop: 10 }}>
            <a className="btn" href={path} download>컴카드 다운로드</a>
          </div>
        </>
      ) : (
        <p className="muted">업로드된 컴카드가 없습니다.</p>
      )}

      {canEdit && (
        <QuickUpload
          actor={actor}
          className="upload-inline"
          accept=".pdf,image/*,.ppt,.pptx"
          buttonLabel="컴카드 업로드"
          hint="pdf / 이미지 / ppt / pptx 업로드 가능 (ppt는 첫 장 미리보기 자동 생성)"
          toFiles={(files) => ({ compcard: files[0] })}
          onDone={onChanged}
        />
      )}
    </div>
  );
}

// ---------- 연기영상 ----------

function VideoPanel({ actor, canEdit }: { actor: Actor; canEdit: boolean }) {
  const { data: videos, error, reload } = useAsync(() => actorsApi.videos(actor.id), [actor.id]);
  const [actionError, setActionError] = useState("");

  async function onDelete(videoId: number) {
    if (!window.confirm("이 영상을 삭제할까요?")) return;
    try {
      await actorsApi.removeVideo(actor.id, videoId);
      reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "삭제하지 못했습니다.");
    }
  }

  return (
    <div className="panel-card">
      <div className="tab-top">
        <div className="panel-title">연기영상 (누적)</div>
      </div>

      <Message error={error || actionError} />

      {videos && videos.length > 0 ? (
        <div className="video-list">
          {videos.map((v) => (
            <div className="video-item" key={v.id}>
              <div className="video-head">
                <div className="video-name">{v.original_name || "video"}</div>
                {canEdit && <button className="btn sm danger" type="button" onClick={() => onDelete(v.id)}>삭제</button>}
              </div>
              <video className="video" controls src={v.video_path} />
            </div>
          ))}
        </div>
      ) : (
        videos && <p className="muted">업로드된 연기영상이 없습니다.</p>
      )}

      {canEdit && (
        <QuickUpload
          actor={actor}
          className="upload-inline"
          accept="video/*"
          multiple
          buttonLabel="연기영상 업로드"
          hint="여러 개 선택 가능 / 기존 영상은 삭제되지 않고 계속 누적됩니다."
          toFiles={(files) => ({ acting_videos: files })}
          onDone={reload}
        />
      )}
    </div>
  );
}
