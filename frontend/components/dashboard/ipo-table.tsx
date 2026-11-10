import Link from "next/link";

import { Badge, gmpTone, statusTone } from "@/components/ui/badge";
import {
  formatCurrency,
  formatDate,
  formatMultiple,
  formatPercent,
  formatPriceBand,
  formatText,
} from "@/lib/format";
import type { IPOSummary } from "@/lib/types";

function GmpCell({ ipo }: { ipo: IPOSummary }) {
  return (
    <div className="space-y-1">
      <Badge tone={gmpTone(ipo.gmp_percent)}>
        {formatPercent(ipo.gmp_percent)}
        {ipo.gmp_percent_derived ? " (derived)" : ""}
      </Badge>
      <p className="text-[11px] text-muted-foreground">
        {formatCurrency(ipo.gmp)}
        {ipo.latest_gmp_source ? ` · ${ipo.latest_gmp_source}` : ""}
      </p>
    </div>
  );
}

export function IpoTable({ items }: { items: IPOSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-[11px] uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="px-5 py-3 font-medium">
              Company
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Status
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Latest GMP
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Issue price
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Size
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Subscribed
            </th>
            <th scope="col" className="px-3 py-3 font-medium">
              Closes
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((ipo) => (
            <tr key={ipo.id} className="align-top hover:bg-muted/40">
              <td className="px-5 py-3">
                <Link
                  href={`/ipos/${ipo.id}`}
                  className="font-medium text-foreground underline-offset-4 hover:text-primary hover:underline"
                >
                  {ipo.name}
                </Link>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {[ipo.category, ipo.sector, ipo.exchange]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
              </td>
              <td className="px-3 py-3">
                <Badge tone={statusTone(ipo.status)}>
                  {formatText(ipo.status)}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <GmpCell ipo={ipo} />
              </td>
              <td className="px-3 py-3">
                {formatPriceBand(
                  ipo.issue_price_lower,
                  ipo.issue_price_upper,
                  ipo.issue_price,
                )}
              </td>
              <td className="px-3 py-3 text-muted-foreground">
                {ipo.ipo_size_cr ? `₹${ipo.ipo_size_cr} cr` : "—"}
              </td>
              <td className="px-3 py-3">
                {formatMultiple(ipo.subscription)}
              </td>
              <td className="px-3 py-3">
                {formatDate(ipo.close_date)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
