/** Auth session storage — JWT lives in HttpOnly cookie (not localStorage). */

const USER_KEY = "quanthire_user";

export type AuthUser = {
  user_id: string;
  email: string;
  name: string;
  role: string;
};

/** @deprecated Token is HttpOnly cookie-only; always returns null in browser JS. */
export function getAccessToken(): string | null {
  return null;
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function persistAuthSession(_accessToken: string, user: AuthUser): void {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(USER_KEY);
}

/** No-op — session cookie is managed by the backend. */
export function syncAuthCookieFromToken(): void {}

export function isAuthenticatedClient(): boolean {
  return Boolean(getStoredUser());
}

export function resolvePostLoginPath(nextPath: string | null | undefined): string {
  if (nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")) {
    return nextPath;
  }
  return "/dashboard";
}
