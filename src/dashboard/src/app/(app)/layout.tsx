import { Nav } from "@/components/Nav";

// Route group (app) — bọc riêng 3 trang tool thật (Overview/Analytics/Topic
// Explorer) bằng topbar + tab pill (Nav.tsx). Landing page ở `/` KHÔNG dùng
// layout này — có LandingNav riêng, không có tab pill.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      {children}
    </>
  );
}
