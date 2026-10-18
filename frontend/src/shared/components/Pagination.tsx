import { Link } from "react-router-dom";

type Props = {
  page: number;
  totalPages: number;
  /** 해당 페이지로 가는 링크 주소 */
  hrefFor: (page: number) => string;
};

const BLOCK_SIZE = 10;

/** 10페이지 단위 블록 페이지네이션 (« ← 1 2 ... 10 → ») */
export function Pagination({ page, totalPages, hrefFor }: Props) {
  if (totalPages <= 1) return null;

  const start = Math.floor((page - 1) / BLOCK_SIZE) * BLOCK_SIZE + 1;
  const end = Math.min(start + BLOCK_SIZE - 1, totalPages);
  const pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  const btn = (label: string, target: number, enabled: boolean) =>
    enabled ? (
      <Link className="page-btn" to={hrefFor(target)}>{label}</Link>
    ) : (
      <span className="page-btn disabled">{label}</span>
    );

  return (
    <div className="pagination">
      {btn("«", 1, page > 1)}
      {btn("←", Math.max(1, start - 1), start > 1)}
      {pages.map((p) =>
        p === page ? (
          <span key={p} className="page-btn active">{p}</span>
        ) : (
          <Link key={p} className="page-btn" to={hrefFor(p)}>{p}</Link>
        )
      )}
      {btn("→", Math.min(totalPages, end + 1), end < totalPages)}
      {btn("»", totalPages, page < totalPages)}
    </div>
  );
}
