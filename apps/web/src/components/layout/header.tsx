"use client";

import { Bell, Search, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/auth-provider";
import { QuantHireLogo } from "@/components/brand/QuantHireLogo";
import { formatRoleLabel } from "@/lib/format-role";

export function Header() {
  const { user, logout } = useAuth();
  const roleLabel = formatRoleLabel(user?.role);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 dark:border-slate-800">
      <div className="flex h-14 w-full items-center gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center lg:hidden">
          <QuantHireLogo
            href="/dashboard"
            variant="nav"
            size="xs"
            surface="light"
            className="max-w-[160px]"
            imageClassName="h-[36px] w-auto max-w-full"
          />
        </div>

        <div className="flex flex-1 items-center justify-end gap-2 sm:justify-between">
          <div className="hidden sm:block flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search candidates, jobs, applications…"
                className="h-9 border-slate-200/80 bg-muted/20 pl-9 dark:border-slate-700"
              />
            </div>
          </div>

          <Button variant="ghost" size="icon">
            <Bell className="h-5 w-5" />
          </Button>

          {roleLabel ? (
            <Badge variant="secondary" className="hidden font-medium sm:inline-flex">
              Role: {roleLabel}
            </Badge>
          ) : null}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Account menu">
                <User className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col gap-1">
                  <span className="truncate">{user?.name || user?.email || "My Account"}</span>
                  {user?.email && user?.name ? (
                    <span className="truncate text-xs font-normal text-muted-foreground">
                      {user.email}
                    </span>
                  ) : null}
                  {roleLabel ? (
                    <span className="text-xs font-semibold tracking-wide text-primary">
                      {roleLabel}
                    </span>
                  ) : null}
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled>Profile</DropdownMenuItem>
              <DropdownMenuItem disabled>Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => void logout()}>
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
