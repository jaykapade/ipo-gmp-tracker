/** Tiny class-name joiner used by the UI primitives. */

export function cn(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(" ");
}
