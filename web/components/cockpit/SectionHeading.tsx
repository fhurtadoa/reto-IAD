import type { ReactNode } from "react";

interface SectionHeadingProps {
  id?: string;
  title: ReactNode;
  cue: ReactNode;
  level?: "h2" | "h3";
}

export default function SectionHeading({ id, title, cue, level: Heading = "h2" }: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <Heading id={id}>{title}</Heading>
      <p className="section-cue">{cue}</p>
    </div>
  );
}
