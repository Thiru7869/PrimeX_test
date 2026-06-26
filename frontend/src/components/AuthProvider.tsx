"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

const PUBLIC_ROUTES = ["/login", "/register"];

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, restore } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  // On first load, try to restore the session via the refresh cookie.
  useEffect(() => {
    restore();
  }, [restore]);

  // Redirect logic, once loading is done.
  useEffect(() => {
    if (isLoading) return;
    const isPublic = PUBLIC_ROUTES.includes(pathname);
    if (!isAuthenticated && !isPublic) {
      router.replace("/login");
    } else if (isAuthenticated && isPublic) {
      router.replace("/chat");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-500">
        Loading…
      </div>
    );
  }
  return <>{children}</>;
}