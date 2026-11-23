"use client";

import React, { useMemo } from "react";
import katex from "katex";

interface KatexBlockProps {
  latex: string;
  displayMode?: boolean;
  className?: string;
}

export default function KatexBlock({ latex, displayMode = true, className = "" }: KatexBlockProps) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, {
        displayMode,
        throwOnError: false,
        strict: false,
      });
    } catch {
      return null;
    }
  }, [latex, displayMode]);

  if (html === null) return <code className={className}>{latex}</code>;

  return (
    <div
      className={`overflow-x-auto cockpit-scroll ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
