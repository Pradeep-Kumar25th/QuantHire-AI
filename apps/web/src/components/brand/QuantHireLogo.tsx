"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

type QuantHireLogoSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl";
type QuantHireLogoVariant = "mark" | "lockup" | "full" | "nav";
type QuantHireLogoSurface = "light" | "dark";

const MARK_SIZE: Record<QuantHireLogoSize, number> = {
  xs: 28,
  sm: 36,
  md: 44,
  lg: 56,
  xl: 72,
  "2xl": 88,
};

const PNG_HEIGHT: Record<"nav" | "full", Record<QuantHireLogoSize, number>> = {
  nav: {
    xs: 30,
    sm: 38,
    md: 46,
    lg: 58,
    xl: 72,
    "2xl": 88,
  },
  full: {
    xs: 36,
    sm: 44,
    md: 56,
    lg: 72,
    xl: 96,
    "2xl": 128,
  },
};

const PNG_WIDTH_RATIO: Record<"nav" | "full", number> = {
  nav: 5.28,
  full: 4.22,
};

const WORDMARK_CLASS: Record<QuantHireLogoSize, string> = {
  xs: "text-sm",
  sm: "text-base",
  md: "text-lg",
  lg: "text-xl",
  xl: "text-2xl",
  "2xl": "text-3xl",
};

const MARK_SRC = "/brand/quanthire-mark.png";
const NAV_SRC = "/brand/quanthire-logo-nav.png";
const FULL_SRC = "/brand/quanthire-logo-full.png";
const NAV_DARK_SRC = "/brand/quanthire-logo-nav-dark.png";
const FULL_DARK_SRC = "/brand/quanthire-logo-full-dark.png";
const ALT = "QuantHireAI — Agentic Hiring Platform · Multi-Agent · Explainable · Evidence-Backed";

export interface QuantHireLogoProps {
  variant?: QuantHireLogoVariant;
  size?: QuantHireLogoSize;
  surface?: QuantHireLogoSurface;
  /** Cap rendered height (keeps aspect ratio — use in nav bars) */
  maxHeight?: number;
  /** Extra classes on the PNG image element */
  imageClassName?: string;
  premium?: boolean;
  className?: string;
  href?: string;
  priority?: boolean;
}

function glossyClassName(surface: QuantHireLogoSurface, premium: boolean) {
  if (!premium) return "";
  return surface === "dark"
    ? "drop-shadow-[0_0_24px_rgba(204,17,47,0.22)] drop-shadow-[0_4px_18px_rgba(35,118,144,0.18)] brightness-[1.03] contrast-[1.04]"
    : "drop-shadow-[0_2px_10px_rgba(0,0,0,0.08)] brightness-[1.02]";
}

function MarkImage({
  size,
  priority,
  className,
  premium,
  surface,
}: {
  size: QuantHireLogoSize;
  priority?: boolean;
  className?: string;
  premium?: boolean;
  surface?: QuantHireLogoSurface;
}) {
  const markSize = MARK_SIZE[size];

  return (
    <div
      className={cn(
        "relative shrink-0 rounded-full bg-gradient-to-br from-[#CC112F]/25 via-transparent to-[#00CCFF]/25 p-[2px]",
        className,
      )}
      style={{ width: markSize + 4, height: markSize + 4 }}
    >
      <div className="h-full w-full overflow-hidden rounded-full bg-transparent">
        <Image
          src={MARK_SRC}
          alt=""
          aria-hidden
          width={markSize}
          height={markSize}
          priority={priority}
          unoptimized
          className={cn(
            "h-full w-full rounded-full object-contain object-center",
            glossyClassName(surface ?? "light", premium ?? true),
          )}
        />
      </div>
    </div>
  );
}

function LockupWordmark({
  size,
  surface,
  showTagline,
}: {
  size: QuantHireLogoSize;
  surface: QuantHireLogoSurface;
  showTagline?: boolean;
}) {
  return (
    <div className="min-w-0 leading-none">
      <div className={cn("font-bold tracking-tight", WORDMARK_CLASS[size])}>
        <span className={surface === "dark" ? "text-white" : "text-slate-900"}>Quant</span>
        <span className={surface === "dark" ? "text-[#38BDF8]" : "text-[#136278]"}>Hire</span>
        <span className="bg-gradient-to-r from-[#FF0033] via-[#CC0099] to-[#00CCFF] bg-clip-text text-transparent ml-0.5">AI</span>
      </div>
      {showTagline && (
        <div
          className={cn(
            "mt-1 text-[9px] font-semibold uppercase tracking-[0.18em]",
            surface === "dark" ? "text-white/60" : "text-slate-500",
          )}
        >
          Agentic Hiring Platform
        </div>
      )}
      {showTagline && (
        <div
          className={cn(
            "mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[8px] font-semibold uppercase tracking-[0.12em]",
            surface === "dark" ? "text-white/55" : "text-slate-500",
          )}
        >
          <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#CC112F]" />Multi-Agent</span>
          <span aria-hidden className="opacity-40">|</span>
          <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#FFB800]" />Explainable</span>
          <span aria-hidden className="opacity-40">|</span>
          <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#00A3FF]" />Evidence-Backed</span>
        </div>
      )}
    </div>
  );
}

function PngLogo({
  src,
  alt,
  height,
  width,
  maxHeight,
  priority,
  surface,
  premium,
  imageClassName,
}: {
  src: string;
  alt: string;
  height: number;
  width: number;
  maxHeight?: number;
  priority?: boolean;
  surface: QuantHireLogoSurface;
  premium: boolean;
  imageClassName?: string;
}) {
  const renderHeight = maxHeight ? Math.min(height, maxHeight) : height;
  const renderWidth = Math.round(renderHeight * (width / height));
  const useInlineSize = !imageClassName;

  return (
    <Image
      src={src}
      alt={alt}
      width={renderWidth}
      height={renderHeight}
      priority={priority}
      unoptimized
      className={cn(
        "block max-w-full object-contain object-left",
        useInlineSize ? "h-auto w-auto" : "h-auto w-auto",
        glossyClassName(surface, premium),
        imageClassName,
      )}
      style={
        useInlineSize
          ? { height: renderHeight, width: "auto", maxWidth: renderWidth }
          : undefined
      }
    />
  );
}

export function QuantHireLogo({
  variant = "nav",
  size = "md",
  surface = "light",
  maxHeight,
  imageClassName,
  premium = true,
  className,
  href,
  priority = false,
}: QuantHireLogoProps) {
  let content: ReactNode;

  const resolvedVariant = variant;
  const showTagline = variant === "full" || variant === "lockup";

  if (resolvedVariant === "mark") {
    content = (
      <MarkImage size={size} priority={priority} premium={premium} surface={surface} />
    );
  } else if (resolvedVariant === "lockup") {
    content = (
      <div className="flex min-w-0 items-center gap-2.5">
        <MarkImage size={size} priority={priority} premium={premium} surface={surface} />
        <LockupWordmark size={size} surface={surface} showTagline={showTagline} />
      </div>
    );
  } else {
    const pngVariant = resolvedVariant === "nav" ? "nav" : "full";
    const height = PNG_HEIGHT[pngVariant][size];
    const width = Math.round(height * PNG_WIDTH_RATIO[pngVariant]);
    const src =
      surface === "dark"
        ? pngVariant === "nav"
          ? NAV_DARK_SRC
          : FULL_DARK_SRC
        : pngVariant === "nav"
        ? NAV_SRC
        : FULL_SRC;

    content = (
      <PngLogo
        src={src}
        alt={ALT}
        height={height}
        width={width}
        maxHeight={maxHeight}
        priority={priority}
        surface={surface}
        premium={premium}
        imageClassName={imageClassName}
      />
    );
  }

  const wrapperClass = cn(
    "inline-flex shrink-0 items-center justify-start",
    className,
  );

  if (href) {
    return (
      <Link href={href} className={wrapperClass} aria-label="QuantHire AI home">
        {content}
      </Link>
    );
  }

  return <div className={wrapperClass}>{content}</div>;
}

export default QuantHireLogo;
