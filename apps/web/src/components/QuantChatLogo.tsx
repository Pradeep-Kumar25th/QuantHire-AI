"use client";

import { cn } from "@/lib/utils";
import { QuantChatAvatar } from "./QuantChatAvatar";

type QuantChatLogoSize = "sm" | "md" | "lg";
type QuantChatLogoVariant = "icon" | "badge" | "mark" | "nav" | "full" | "lockup";

const AVATAR_SIZE = {
  sm: "sm" as const,
  md: "md" as const,
  lg: "lg" as const,
};

interface QuantChatLogoProps {
  size?: QuantChatLogoSize;
  className?: string;
  variant?: QuantChatLogoVariant;
  circular?: boolean;
}

export function QuantChatLogo({
  size = "md",
  className = "",
  variant = "badge",
  circular,
}: QuantChatLogoProps) {
  if (variant === "nav" || variant === "full" || variant === "lockup") {
    const avatarSize = size === "lg" ? "md" : size === "md" ? "sm" : "xs";

    return (
      <div className={cn("flex items-center gap-2.5 min-w-0 shrink-0", className)}>
        <QuantChatAvatar
          size={avatarSize}
          variant="badge"
          glow
        />
        <div className="flex flex-col min-w-0 leading-none select-none">
          <div className="flex items-center font-bold tracking-tight text-white drop-shadow-sm text-base">
            <span>Quant</span>
            <span className="bg-gradient-to-r from-[#FF0055] via-[#CC00FF] to-[#00D2FF] bg-clip-text text-transparent">Chat</span>
          </div>
          <span className="text-[9.5px] font-semibold tracking-widest text-white/90 uppercase mt-0.5">
            AI Chatbot
          </span>
        </div>
      </div>
    );
  }

  return (
    <QuantChatAvatar
      size={AVATAR_SIZE[size]}
      variant="badge"
      glow={variant === "badge" || !circular}
      className={cn("transition-transform duration-300 hover:scale-105", className)}
    />
  );
}

export default QuantChatLogo;
