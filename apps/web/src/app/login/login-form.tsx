"use client";



import { useEffect, useState } from "react";

import Link from "next/link";

import { useRouter, useSearchParams } from "next/navigation";



import { useAuth } from "@/contexts/auth-provider";

import { resolvePostLoginPath } from "@/lib/auth-storage";

import { fetchSsoConfig, SsoConfig } from "@/lib/msal-auth";

import { ApiError } from "@/lib/api-client";

import { Button } from "@/components/ui/button";

import { QuantHireLogo } from "@/components/brand/QuantHireLogo";

import { Input } from "@/components/ui/input";

import { Label } from "@/components/ui/label";



export default function LoginForm() {

  const { login, loginWithEntra, isAuthenticated, isLoading } = useAuth();

  const router = useRouter();

  const searchParams = useSearchParams();

  const nextPath = searchParams.get("next");

  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [error, setError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);

  const [ssoSubmitting, setSsoSubmitting] = useState(false);

  const [ssoConfig, setSsoConfig] = useState<SsoConfig | null>(null);



  useEffect(() => {

    void fetchSsoConfig().then(setSsoConfig);

  }, []);



  useEffect(() => {

    if (!isLoading && isAuthenticated) {

      router.replace(resolvePostLoginPath(nextPath));

    }

  }, [isAuthenticated, isLoading, nextPath, router]);



  if (!isLoading && isAuthenticated) {

    return (

      <div className="flex min-h-screen items-center justify-center">

        <p className="text-muted-foreground">Redirecting to dashboard...</p>

      </div>

    );

  }



  const onSubmit = async (event: React.FormEvent) => {

    event.preventDefault();

    setError(null);

    setSubmitting(true);

    try {

      await login({ email, password }, { redirectTo: nextPath });

    } catch (err) {

      const message =

        err instanceof Error ? err.message : "Login failed. Check your credentials.";

      setError(message);

    } finally {

      setSubmitting(false);

    }

  };



  const onMicrosoftSignIn = async () => {

    setError(null);

    setSsoSubmitting(true);

    try {

      await loginWithEntra({ redirectTo: nextPath });

    } catch (err) {
      let message =
        err instanceof Error
          ? err.message
          : "Microsoft sign-in failed. Please try again.";
      if (err instanceof ApiError && err.message) {
        message = err.message;
      }
      if (
        err instanceof Error &&
        "errorCode" in err &&
        typeof (err as { errorCode?: string }).errorCode === "string"
      ) {
        const code = (err as { errorCode: string }).errorCode;
        if (code === "popup_window_error" || code === "user_cancelled") {
          message =
            "Microsoft sign-in was blocked or cancelled. Allow popups for this site and try again.";
        }
      }
      setError(message);

    } finally {

      setSsoSubmitting(false);

    }

  };



  const ssoEnabled = Boolean(

    ssoConfig?.enabled && ssoConfig.client_id && ssoConfig.tenant_id

  );



  return (

    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">

      <div className="w-full max-w-md space-y-6 rounded-lg border bg-background p-8 shadow-sm">

        <div className="space-y-3 text-center">

          <div className="flex justify-center px-2">

            <QuantHireLogo
              variant="nav"
              size="md"
              surface="light"
              premium
              className="mx-auto max-w-[min(100%,300px)]"
              imageClassName="h-[56px] w-auto max-w-full object-contain"
            />

          </div>

          <p className="text-sm text-muted-foreground">

            Sign in with your Malomatia account

          </p>

        </div>



        {ssoEnabled ? (

          <div className="space-y-3">

            <Button

              type="button"

              variant="outline"

              className="w-full"

              disabled={ssoSubmitting || submitting}

              onClick={() => void onMicrosoftSignIn()}

            >

              {ssoSubmitting ? "Signing in with Microsoft..." : "Sign in with Microsoft"}

            </Button>

            <div className="relative">

              <div className="absolute inset-0 flex items-center">

                <span className="w-full border-t" />

              </div>

              <div className="relative flex justify-center text-xs uppercase">

                <span className="bg-background px-2 text-muted-foreground">

                  Or continue with email

                </span>

              </div>

            </div>

          </div>

        ) : null}



        <form onSubmit={onSubmit} className="space-y-4">

          <div className="space-y-2">

            <Label htmlFor="email">Email</Label>

            <Input

              id="email"

              type="email"

              autoComplete="email"
              maxLength={255}
              value={email}

              onChange={(e) => setEmail(e.target.value)}

              required={!ssoEnabled}

            />

          </div>

          <div className="space-y-2">

            <Label htmlFor="password">Password</Label>

            <Input

              id="password"

              type="password"

              autoComplete="current-password"
              maxLength={128}
              value={password}

              onChange={(e) => setPassword(e.target.value)}

              required={!ssoEnabled}

            />

          </div>



          {error ? (

            <p className="text-sm text-destructive" role="alert">

              {error}

            </p>

          ) : null}



          <Button type="submit" className="w-full" disabled={submitting || ssoSubmitting}>

            {submitting ? "Signing in..." : "Sign in with email"}

          </Button>

        </form>



        <p className="text-center text-sm text-muted-foreground">

          <Link href="/" className="underline underline-offset-4">

            Back to home

          </Link>

        </p>

      </div>

    </div>

  );

}

