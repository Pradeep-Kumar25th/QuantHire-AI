import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { RequireAuth } from "@/components/auth/require-auth";
import QuantChat from "@/components/QuantChat";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen w-full bg-background">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 min-w-0 overflow-x-hidden bg-slate-50/40 dark:bg-background">
            {children}
          </main>
        </div>
        <QuantChat />
      </div>
    </RequireAuth>
  );
}
