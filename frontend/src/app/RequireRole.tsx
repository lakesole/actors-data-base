import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { Role } from "../features/auth/types";
import { Loading } from "../shared/components/Message";
import { useAuth } from "./AuthContext";

type Props = {
  /** 비우면 로그인만 확인한다 */
  roles?: Role[];
  children: ReactNode;
};

/** 로그인/역할이 필요한 화면을 감싼다. 서버도 같은 검사를 하므로 화면 표시용이다. */
export function RequireRole({ roles, children }: Props) {
  const { user } = useAuth();
  const location = useLocation();

  if (user === undefined) return <Loading />;

  if (user === null) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <p className="muted">이 화면을 볼 권한이 없습니다.</p>;
  }

  return <>{children}</>;
}
