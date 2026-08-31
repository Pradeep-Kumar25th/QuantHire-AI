"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

type QuantChatAvatarSize = "xs" | "sm" | "md" | "lg";
type QuantChatAvatarVariant = "icon" | "badge";

const SIZE_MAP: Record<
  QuantChatAvatarSize,
  { px: number; ring: string; pad: string }
> = {
  xs: { px: 32, ring: "ring-1 ring-fuchsia-500/30", pad: "p-[1.5px]" },
  sm: { px: 40, ring: "ring-1.5 ring-fuchsia-500/35", pad: "p-[2px]" },
  md: { px: 50, ring: "ring-2 ring-fuchsia-500/40", pad: "p-[2px]" },
  lg: { px: 68, ring: "ring-2 ring-fuchsia-400/50", pad: "p-[3px]" },
};

const LOGO_SRC = "/brand/quantchat-circle.png";

const GLOSS =
  "brightness-[1.04] contrast-[1.05] saturate-[1.08] drop-shadow-[0_2px_10px_rgba(139,92,246,0.35)]";

export interface QuantChatAvatarProps {
  size?: QuantChatAvatarSize;
  /** icon or badge */
  variant?: QuantChatAvatarVariant;
  className?: string;
  glow?: boolean;
}

/** Circular QuantChat logo — crisp, glossy, perfectly round. */
export function QuantChatAvatar({
  size = "xs",
  variant = "badge",
  className,
  glow = false,
}: QuantChatAvatarProps) {
  const { px, ring, pad } = SIZE_MAP[size];

  return (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-full aspect-square bg-gradient-to-br from-fuchsia-500/30 via-violet-500/20 to-cyan-500/30",
        pad,
        ring,
        glow && "shadow-[0_0_24px_rgba(168,85,247,0.45),0_6px_20px_rgba(34,211,238,0.25)]",
        className,
      )}
      style={{ width: px, height: px, minWidth: px, minHeight: px }}
      aria-hidden
    >
      <div className="relative h-full w-full overflow-hidden rounded-full aspect-square bg-[#0a0a0f]">
        <Image
          src={LOGO_SRC}
          alt="QuantChat AI"
          width={px}
          height={px}
          unoptimized
          priority={size === "lg" || size === "md"}
          className={cn(
            "h-full w-full object-cover object-center rounded-full",
            GLOSS,
          )}
        />
      </div>
    </div>
  );
}

export default QuantChatAvatar;
