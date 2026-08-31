"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { apiFetchJson, ApiError } from "@/lib/api-client";
import {
  fetchSsoConfig,
  loginWithMicrosoft,
  logoutMicrosoft,
  SsoConfig,
} from "@/lib/msal-auth";
import {
  AuthUser,
  clearAuthSession,
  getStoredUser,
  persistAuthSession,
  resolvePostLoginPath,
} from "@/lib/auth-storage";

type LoginPayload = {
  email: string;
  password: string;
};

type LoginOptions = {
  redirectTo?: string | null;
};

type TokenResponse = {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload, options?: LoginOptions) => Promise<void>;
  loginWithEntra: (options?: LoginOptions) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const bootstrapStarted = useRef(false);

  const refreshUser = useCallback(async () => {
    try {
      const me = await apiFetchJson<{
        id: string;
        email: string;
        name: string;
        role: string;
      }>("/v1/auth/me");
      setUser({
        user_id: me.id,
        email: me.email,
        name: me.name,
        role: me.role,
      });
    } catch {
      clearAuthSession();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    if (bootstrapStarted.current) {
      return;
    }
    bootstrapStarted.current = true;

    const bootstrap = async () => {
      const stored = getStoredUser();
      if (stored) {
        setUser(stored);
      }
      await refreshUser();
      setIsLoading(false);
    };
    void bootstrap();
  }, [refreshUser]);

  const login = useCallback(
    async (payload: LoginPayload, options?: LoginOptions) => {
      const result = await apiFetchJson<TokenResponse>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const authUser: AuthUser = {
        user_id: result.user_id,
        email: result.email,
        name: result.name,
        role: result.role,
      };

      persistAuthSession(result.access_token, authUser);
      setUser(authUser);

      router.replace(resolvePostLoginPath(options?.redirectTo ?? null));
    },
    [router]
  );

  const loginWithEntra = useCallback(
    async (options?: LoginOptions) => {
      const ssoConfig: SsoConfig = await fetchSsoConfig();
      if (!ssoConfig.enabled || !ssoConfig.client_id || !ssoConfig.tenant_id) {
        throw new Error("Microsoft SSO is not enabled on this environment");
      }

      const entraIdToken = await loginWithMicrosoft(ssoConfig);
      let result: TokenResponse;
      try {
        result = await apiFetchJson<TokenResponse>("/v1/auth/entra/callback", {
          method: "POST",
          body: JSON.stringify({ id_token: entraIdToken }),
        });
      } catch (error) {
        if (error instanceof ApiError && error.message) {
          throw new Error(error.message);
        }
        throw error;
      }

      const authUser: AuthUser = {
        user_id: result.user_id,
        email: result.email,
        name: result.name,
        role: result.role,
      };

      persistAuthSession(result.access_token, authUser);
      setUser(authUser);

      // Hardened NPD: JWT is HttpOnly cookie-only — verify /me before redirect.
      try {
        const me = await apiFetchJson<{
          id: string;
          email: string;
          name: string;
          role: string;
        }>("/v1/auth/me");
        const verified: AuthUser = {
          user_id: me.id,
          email: me.email,
          name: me.name,
          role: me.role,
        };
        persistAuthSession(result.access_token, verified);
        setUser(verified);
      } catch {
        clearAuthSession();
        setUser(null);
        throw new Error(
          "Microsoft sign-in succeeded but QuantHire session could not be verified. " +
            "Allow cookies for this site and retry."
        );
      }

      router.replace(resolvePostLoginPath(options?.redirectTo ?? null));
    },
    [router]
  );

  const logout = useCallback(async () => {
    let ssoConfig: SsoConfig = { enabled: false };
    try {
      ssoConfig = await fetchSsoConfig();
    } catch {
      // ignore
    }
    try {
      await apiFetchJson("/v1/auth/logout", { method: "POST" });
    } catch {
      // ignore — clear local session regardless
    }
    await logoutMicrosoft(ssoConfig);
    clearAuthSession();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      loginWithEntra,
      logout,
      refreshUser,
    }),
    [user, isLoading, login, loginWithEntra, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
