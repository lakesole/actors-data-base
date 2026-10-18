import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Loading, Message } from "../../shared/components/Message";
import { defaultContractEndDate, digitsOnly, formatDateTyping } from "../../shared/format";
import { useAsync } from "../../shared/hooks/useAsync";
import { teachersApi } from "../teachers/api";
import { actorsApi, fieldsFromActor } from "./api";
import { readListParams, toSearch } from "./listParams";
import type { ActorFields } from "./types";

const EMPTY: ActorFields = {
  name: "", manager_name: "", teacher_user_id: "", phone_last4: "", gender: "", birth_year: "",
  height_cm: "", weight_kg: "", school: "", hobby: "", specialty: "", contract_date: "", contract_end_date: "", bio: "",
};

/** 배우 추가(/actors/new)와 수정(/actors/:actorId/edit) */
export function ActorFormPage() {
  const navigate = useNavigate();
  const params = useParams();
  const [search] = useSearchParams();
  const actorId = params.actorId ? Number(params.actorId) : null;
  const isNew = actorId === null;
  const listSearch = toSearch(readListParams(search));

  const teachers = useAsync(() => teachersApi.choices(), []);
  const [fields, setFields] = useState<ActorFields>(EMPTY);
  const [photo, setPhoto] = useState<File | null>(null);
  const [compcard, setCompcard] = useState<File | null>(null);
  const [videos, setVideos] = useState<File[]>([]);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (actorId === null) return;
    actorsApi
      .get(actorId)
      .then((actor) => setFields(fieldsFromActor(actor)))
      .catch((e) => setError(e instanceof Error ? e.message : "배우 정보를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [actorId]);

  const set = (key: keyof ActorFields) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setFields((f) => ({ ...f, [key]: e.target.value }));

  const setDigits = (key: keyof ActorFields, max: number) => (e: ChangeEvent<HTMLInputElement>) =>
    setFields((f) => ({ ...f, [key]: digitsOnly(e.target.value, max) }));

  function onContractDate(e: ChangeEvent<HTMLInputElement>) {
    const value = formatDateTyping(e.target.value);
    // 새로 등록할 때는 계약 만료일을 1년 뒤로 자동으로 채운다
    setFields((f) => ({ ...f, contract_date: value, ...(isNew ? { contract_end_date: defaultContractEndDate(value) } : {}) }));
  }

  const detailUrl = actorId ? `/actors/${actorId}${listSearch}` : "/";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const files = { photo, compcard, acting_videos: videos };
      if (actorId === null) {
        const { id } = await actorsApi.create(fields, files);
        navigate(`/actors/${id}`);
      } else {
        await actorsApi.update(actorId, fields, files);
        navigate(detailUrl);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장하지 못했습니다.");
      setSaving(false);
    }
  }

  if (loading) return <Loading />;

  return (
    <>
      <div className="detail-top">
        <Link className="back" to={detailUrl}>{isNew ? "← 목록으로" : "← 상세페이지"}</Link>
      </div>

      <div className="form-wrap">
        <h1 className="form-title">{isNew ? "배우 추가" : "배우정보 수정"}</h1>
        <Message error={error || teachers.error} />

        <form className="form" onSubmit={onSubmit}>
          <div className="grid-form">
            <div className="field">
              <label>이름 *</label>
              <input type="text" required placeholder="예: 김철수" value={fields.name} onChange={set("name")} />
            </div>

            <div className="field">
              <label>담당 매니저</label>
              <input type="text" placeholder="예: 곽다윗" value={fields.manager_name} onChange={set("manager_name")} />
            </div>

            <div className="field">
              <label>담당 선생님</label>
              <select value={fields.teacher_user_id} onChange={set("teacher_user_id")}>
                <option value="">미지정</option>
                {(teachers.data ?? []).map((t) => (
                  <option key={t.id} value={String(t.id)}>
                    {t.display_name}
                    {t.lesson_subject ? ` · ${t.lesson_subject}` : ""}
                    {t.lesson_days ? ` (${t.lesson_days})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>전화번호 뒤 4자리</label>
              <input type="text" inputMode="numeric" maxLength={4} placeholder="예: 1234" value={fields.phone_last4} onChange={setDigits("phone_last4", 4)} />
            </div>

            <div className="field">
              <label>성별</label>
              <select value={fields.gender} onChange={set("gender")}>
                <option value="">선택</option>
                <option value="남자">남자</option>
                <option value="여자">여자</option>
              </select>
            </div>

            <div className="field year-field">
              <label>년생</label>
              <input type="text" inputMode="numeric" maxLength={4} minLength={4} pattern="[0-9]{4}" placeholder="예: 1998" value={fields.birth_year} onChange={setDigits("birth_year", 4)} />
            </div>

            <div className="field">
              <label>키(cm)</label>
              <input type="number" step="0.1" placeholder="예: 178" value={fields.height_cm} onChange={set("height_cm")} />
            </div>

            <div className="field">
              <label>몸무게(kg)</label>
              <input type="number" step="0.1" placeholder="예: 70" value={fields.weight_kg} onChange={set("weight_kg")} />
            </div>

            <div className="field">
              <label>학교</label>
              <input type="text" placeholder="예: 한예종 연기과" value={fields.school} onChange={set("school")} />
            </div>

            <div className="field">
              <label>취미</label>
              <input type="text" placeholder="예: 헬스, 농구" value={fields.hobby} onChange={set("hobby")} />
            </div>

            <div className="field full">
              <label>특기</label>
              <input type="text" placeholder="예: 액션, 노래, 중국어" value={fields.specialty} onChange={set("specialty")} />
            </div>

            <div className="field date-field">
              <label>계약 시작일</label>
              <input type="text" className="date-text" inputMode="numeric" maxLength={10} placeholder="YYYY-MM-DD" value={fields.contract_date} onChange={onContractDate} />
            </div>

            <div className="field date-field">
              <label>계약 만료일</label>
              <input
                type="text"
                className="date-text"
                inputMode="numeric"
                maxLength={10}
                placeholder="YYYY-MM-DD"
                value={fields.contract_end_date}
                onChange={(e) => setFields((f) => ({ ...f, contract_end_date: formatDateTyping(e.target.value) }))}
              />
            </div>

            <div className="field full">
              <label>메모</label>
              <textarea rows={4} placeholder="메모를 입력하세요" value={fields.bio} onChange={set("bio")} />
            </div>
          </div>

          <div className="upload-block">
            <div className="upload-title">파일 관리 (선택)</div>
            <div className="upload-row upload-row-3">
              <div className="u">
                <div className="u-label">{isNew ? "프로필 사진" : "프로필 사진 (올리면 교체)"}</div>
                <input className="file" type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </div>
              <div className="u">
                <div className="u-label">{isNew ? "컴카드 (PDF/이미지/PPT/PPTX)" : "컴카드 (올리면 교체)"}</div>
                <input className="file" type="file" accept=".pdf,image/*,.ppt,.pptx" onChange={(e) => setCompcard(e.target.files?.[0] ?? null)} />
              </div>
              <div className="u">
                <div className="u-label">{isNew ? "연기영상 (여러 개 가능)" : "연기영상 (올리면 누적 추가, 여러 개 가능)"}</div>
                <input className="file" type="file" accept="video/*" multiple onChange={(e) => setVideos(Array.from(e.target.files ?? []))} />
              </div>
            </div>
            <div className="upload-hint">연기영상은 기존 영상이 삭제되지 않고 계속 누적됩니다.</div>
          </div>

          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
            <Link className="btn" to={detailUrl}>취소</Link>
          </div>
        </form>
      </div>
    </>
  );
}
