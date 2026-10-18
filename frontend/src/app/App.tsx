import { Navigate, Route, Routes } from "react-router-dom";
import { RecordFormPage } from "../features/actor_records/RecordFormPage";
import { ActorDetailPage } from "../features/actors/ActorDetailPage";
import { ActorFormPage } from "../features/actors/ActorFormPage";
import { ActorListPage } from "../features/actors/ActorListPage";
import { AttendancePage } from "../features/attendance/AttendancePage";
import { KioskPage } from "../features/attendance/KioskPage";
import { LoginPage } from "../features/auth/LoginPage";
import { PasswordPage } from "../features/auth/PasswordPage";
import { AdminPage } from "../features/users/AdminPage";
import { Layout } from "./Layout";
import { RequireRole } from "./RequireRole";

export function App() {
  return (
    <Routes>
      {/* 태블릿 출결은 상단바 없이 전체 화면 */}
      <Route path="/attendance/kiosk" element={<RequireRole roles={["admin"]}><KioskPage /></RequireRole>} />

      <Route element={<Layout />}>
        <Route path="/" element={<ActorListPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/account/password" element={<RequireRole><PasswordPage /></RequireRole>} />
        <Route path="/admin/users" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />

        <Route path="/actors/new" element={<RequireRole roles={["admin", "staff"]}><ActorFormPage /></RequireRole>} />
        <Route path="/actors/:actorId" element={<ActorDetailPage />} />
        <Route path="/actors/:actorId/edit" element={<RequireRole roles={["admin", "staff"]}><ActorFormPage /></RequireRole>} />
        <Route path="/actors/:actorId/records/:path/new" element={<RequireRole><RecordFormPage /></RequireRole>} />
        <Route path="/actors/:actorId/records/:path/:itemId/edit" element={<RequireRole><RecordFormPage /></RequireRole>} />

        <Route path="/attendance" element={<RequireRole><AttendancePage /></RequireRole>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
