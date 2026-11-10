/** Display helpers. All dates are rendered in IST unless noted otherwise. */

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

const number = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
});

const dateOnly = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const dateTime = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
  timeZone: "Asia/Kolkata",
});

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function parseDate(value: string): Date | null {
  const parsed = new Date(
    DATE_PATTERN.test(value) ? `${value}T00:00:00Z` : value,
  );
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatCurrency(value: number | null | undefined): string {
  return value == null ? "—" : currency.format(value);
}

export function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : number.format(value);
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  return value == null ? "—" : `${value.toFixed(digits)}%`;
}

export function formatMultiple(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toFixed(2)}×`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = parseDate(value);
  return parsed ? dateOnly.format(parsed) : value;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = parseDate(value);
  return parsed ? `${dateTime.format(parsed)} IST` : value;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatPriceBand(
  lower: number | null | undefined,
  upper: number | null | undefined,
  issuePrice: number | null | undefined,
): string {
  if (lower != null && upper != null) {
    return `${formatCurrency(lower)} – ${formatCurrency(upper)}`;
  }
  return formatCurrency(upper ?? issuePrice);
}

export function formatText(value: string | null | undefined): string {
  return value?.trim() ? value : "—";
}
