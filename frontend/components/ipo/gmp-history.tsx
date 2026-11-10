import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDateTime, formatPercent } from "@/lib/format";
import type { GMPPoint } from "@/lib/types";

export function GmpHistory({ history }: { history: GMPPoint[] }) {
  if (history.length === 0) {
    return (
      <p className="px-5 py-8 text-center text-sm text-muted-foreground">
        No GMP observations have been stored for this IPO yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-[11px] uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="px-5 py-2.5 font-medium">
              Recorded
            </th>
            <th scope="col" className="px-3 py-2.5 font-medium">
              Source
            </th>
            <th scope="col" className="px-3 py-2.5 font-medium">
              GMP
            </th>
            <th scope="col" className="px-3 py-2.5 font-medium">
              GMP %
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {history.map((point) => (
            <tr key={`${point.source}-${point.recorded_at}`}>
              <td className="px-5 py-2.5 text-muted-foreground">
                {formatDateTime(point.recorded_at)}
              </td>
              <td className="px-3 py-2.5">{point.source}</td>
              <td className="px-3 py-2.5">{formatCurrency(point.gmp)}</td>
              <td className="px-3 py-2.5">
                <Badge>{formatPercent(point.gmp_percent)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
