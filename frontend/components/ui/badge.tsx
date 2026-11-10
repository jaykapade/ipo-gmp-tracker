import { cn } from "@/lib/utils";

export type BadgeTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "primary";

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-info/30 bg-info/10 text-info",
  primary: "border-primary/30 bg-primary/10 text-primary",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string | null | undefined): BadgeTone {
  switch (status?.toLowerCase()) {
    case "open":
      return "success";
    case "upcoming":
      return "warning";
    case "listed":
      return "info";
    case "closed":
    case "withdrawn":
    case "cancelled":
      return "neutral";
    default:
      return "neutral";
  }
}

export function verdictTone(verdict: string | null | undefined): BadgeTone {
  switch (verdict) {
    case "Strong":
      return "success";
    case "Watch":
      return "warning";
    case "Avoid":
      return "danger";
    default:
      return "neutral";
  }
}

export function checklistTone(status: string): BadgeTone {
  switch (status) {
    case "pass":
      return "success";
    case "warn":
      return "warning";
    case "fail":
      return "danger";
    default:
      return "neutral";
  }
}

export function gmpTone(percent: number | null | undefined): BadgeTone {
  if (percent == null) return "neutral";
  if (percent >= 20) return "success";
  if (percent > 0) return "warning";
  return "danger";
}
