/**
 * MSAL (Entra ID) helpers for QuantHire SSO.
 * Client id / tenant come from GET /v1/auth/sso-config at runtime (no rebuild per env).
 */

import {
  BrowserAuthError,
  Configuration,
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";

export type SsoConfig = {
  enabled: boolean;
  client_id?: string | null;
  tenant_id?: string | null;
  scopes?: string[];
};

const DEFAULT_SCOPES = ["openid", "profile", "email", "User.Read"];

let msalApp: PublicClientApplication | null = null;
let msalConfigKey = "";

function getRedirectUri(): string | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  // Match Entra redirect URI registration (origin only, no path).
  return window.location.origin;
}

function clearStaleMsalRedirectState(): void {
  if (typeof window === "undefined") {
    return;
  }
  // If Entra redirected with a fragment, keep it for handleRedirectPromise.
  if (window.location.hash.length > 1) {
    return;
  }
  for (const key of Object.keys(sessionStorage)) {
    if (key.includes("interaction.status") || key.includes("request.origin")) {
      sessionStorage.removeItem(key);
    }
  }
}

function isBenignRedirectError(error: unknown): boolean {
  return (
    error instanceof BrowserAuthError &&
    (error.errorCode === "hash_empty_error" ||
      error.errorCode === "no_hash_found" ||
      error.errorCode === "empty_hash_error")
  );
}

function buildMsalConfig(config: SsoConfig): Configuration {
  const clientId = config.client_id ?? "";
  const tenantId = config.tenant_id ?? "common";
  return {
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId}`,
      redirectUri: getRedirectUri(),
      postLogoutRedirectUri:
        typeof window !== "undefined" ? `${window.location.origin}/login` : undefined,
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: "sessionStorage",
      storeAuthStateInCookie: false,
    },
  };
}

export async function fetchSsoConfig(): Promise<SsoConfig> {
  const response = await fetch("/api/v1/auth/sso-config", {
    credentials: "same-origin",
  });
  if (!response.ok) {
    return { enabled: false, scopes: [] };
  }
  return (await response.json()) as SsoConfig;
}

export async function getMsalInstance(config: SsoConfig): Promise<PublicClientApplication> {
  const key = `${config.client_id}:${config.tenant_id}`;
  if (msalApp && msalConfigKey === key) {
    return msalApp;
  }

  clearStaleMsalRedirectState();
  msalApp = new PublicClientApplication(buildMsalConfig(config));

  try {
    await msalApp.initialize();
  } catch (error) {
    if (!isBenignRedirectError(error)) {
      throw error;
    }
  }

  try {
    await msalApp.handleRedirectPromise();
  } catch (error) {
    if (!isBenignRedirectError(error)) {
      throw error;
    }
  }

  msalConfigKey = key;
  return msalApp;
}

/** Complete Entra redirect (if any) and return an ID token, or null for popup-only flows. */
export async function acquireEntraIdTokenFromRedirect(
  config: SsoConfig
): Promise<string | null> {
  if (!config.enabled || !config.client_id || !config.tenant_id) {
    return null;
  }

  const instance = await getMsalInstance(config);
  let result;
  try {
    result = await instance.handleRedirectPromise();
  } catch (error) {
    if (isBenignRedirectError(error)) {
      return null;
    }
    throw error;
  }

  if (result?.idToken) {
    return result.idToken;
  }

  const accounts = instance.getAllAccounts();
  if (accounts.length === 0) {
    return null;
  }

  const scopes = config.scopes?.length ? config.scopes : DEFAULT_SCOPES;
  try {
    const silent = await instance.acquireTokenSilent({ scopes, account: accounts[0] });
    return silent.idToken ?? null;
  } catch {
    return null;
  }
}

export async function loginWithMicrosoft(config: SsoConfig): Promise<string> {
  const instance = await getMsalInstance(config);
  const scopes = config.scopes?.length ? config.scopes : DEFAULT_SCOPES;

  // Interactive login — always request a fresh ID token (includes Entra app ``roles`` claim).
  const popup = await instance.loginPopup({
    scopes,
    prompt: "login",
    redirectUri: getRedirectUri(),
  });
  const account = popup.account ?? instance.getAllAccounts()[0];
  if (!account) {
    throw new Error("Microsoft sign-in did not return an account");
  }

  if (popup.idToken) {
    return popup.idToken;
  }

  try {
    const token = await instance.acquireTokenSilent({ scopes, account });
    if (token.idToken) {
      return token.idToken;
    }
  } catch (error) {
    if (!(error instanceof InteractionRequiredAuthError)) {
      throw error;
    }
  }

  const tokenPopup = await instance.acquireTokenPopup({ scopes, account });
  if (!tokenPopup.idToken) {
    throw new Error("Microsoft sign-in did not return an ID token");
  }
  return tokenPopup.idToken;
}

export async function logoutMicrosoft(config: SsoConfig): Promise<void> {
  if (!config.enabled || !config.client_id) {
    return;
  }
  try {
    const instance = await getMsalInstance(config);
    const accounts = instance.getAllAccounts();
    if (accounts.length > 0) {
      await instance.logoutPopup({ account: accounts[0] });
    }
  } catch {
    // Best-effort — local QuantHire session is cleared separately.
  }
}
