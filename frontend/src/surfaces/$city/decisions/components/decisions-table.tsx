/**
 * SYNAPSE Atlas Console — Decision Trace virtualised table.
 *
 * TanStack Table for the column model + @tanstack/react-virtual for the
 * row virtualiser. Infinite scroll triggers `onLoadMore` when within the
 * last `LOAD_MORE_THRESHOLD` rows of the visible window.
 */
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";

import { Badge, tierBadgeVariant } from "@shared/ui/badge";
import { cn } from "@shared/ui/cn";

import type { RecentDecisionRow } from "../model/decision";

const LOAD_MORE_THRESHOLD = 10;
const ROW_HEIGHT = 44;

export interface DecisionsTableProps {
  readonly rows: readonly RecentDecisionRow[];
  readonly hasNextPage: boolean;
  readonly isFetching: boolean;
  readonly onLoadMore: () => void;
  readonly onRowOpen: (decisionId: string) => void;
  readonly openId: string | null;
  readonly className?: string;
}

export function DecisionsTable({
  rows,
  hasNextPage,
  isFetching,
  onLoadMore,
  onRowOpen,
  openId,
  className,
}: DecisionsTableProps) {
  const { t } = useTranslation();
  const parentRef = useRef<HTMLDivElement>(null);

  const columns = useMemo<ColumnDef<RecentDecisionRow>[]>(
    () => [
      {
        accessorKey: "tier",
        header: () => t("decisionTrace.table.tier"),
        cell: (ctx) => (
          <Badge variant={tierBadgeVariant(ctx.getValue<RecentDecisionRow["tier"]>())}>
            {ctx.getValue<string>()}
          </Badge>
        ),
        size: 96,
      },
      {
        accessorKey: "decision_id",
        header: () => t("decisionTrace.table.decisionId"),
        cell: (ctx) => (
          <span className="font-mono text-ops-xs">
            {ctx.getValue<string>().slice(0, 8)}…
          </span>
        ),
        size: 140,
      },
      {
        accessorKey: "audit_id",
        header: () => "Audit ID",
        cell: (ctx) => (
          <span className="font-mono text-ops-xs text-muted-fg">
            {ctx.getValue<string>().slice(0, 8)}…
          </span>
        ),
        size: 140,
      },
      {
        accessorKey: "created_at",
        header: () => t("decisionTrace.table.createdAt"),
        cell: (ctx) => (
          <time
            dateTime={ctx.getValue<string>()}
            className="tabular-nums text-ops-sm text-muted-fg"
          >
            {new Date(ctx.getValue<string>()).toLocaleString("en-IN", {
              timeZone: "Asia/Kolkata",
              hour12: false,
            })}
          </time>
        ),
        size: 240,
      },
    ],
    [t],
  );

  const table = useReactTable({
    data: rows as RecentDecisionRow[],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const tableRows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  // Trigger load-more when the virtualizer surfaces near the tail.
  useEffect(() => {
    const items = virtualizer.getVirtualItems();
    const lastItem = items[items.length - 1];
    if (!lastItem) return;
    if (
      lastItem.index >= tableRows.length - LOAD_MORE_THRESHOLD &&
      hasNextPage &&
      !isFetching
    ) {
      onLoadMore();
    }
  }, [virtualizer, tableRows.length, hasNextPage, isFetching, onLoadMore]);

  const totalSize = virtualizer.getTotalSize();
  const items = virtualizer.getVirtualItems();
  const paddingTop = items[0]?.start ?? 0;
  const paddingBottom = totalSize - (items[items.length - 1]?.end ?? 0);

  return (
    <div
      ref={parentRef}
      className={cn(
        "h-full overflow-auto rounded-md border border-border bg-card",
        className,
      )}
      role="region"
      aria-label={t("decisionTrace.title")}
    >
      <table className="w-full border-collapse text-ops-sm">
        <thead className="sticky top-0 z-10 bg-card">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="text-left">
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  style={{ width: h.column.getSize() }}
                  className="border-b border-border px-3 py-2 text-ops-xs uppercase tracking-wide text-muted-fg"
                  scope="col"
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {paddingTop > 0 && (
            <tr aria-hidden="true">
              <td colSpan={columns.length} style={{ height: paddingTop }} />
            </tr>
          )}
          {items.map((vi) => {
            const row = tableRows[vi.index];
            if (!row) return null;
            const isOpen = row.original.decision_id === openId;
            return (
              <tr
                key={row.id}
                tabIndex={0}
                onClick={() => onRowOpen(row.original.decision_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRowOpen(row.original.decision_id);
                  }
                }}
                className={cn(
                  "cursor-pointer border-b border-border outline-none hover:bg-muted/40 focus-visible:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring",
                  isOpen && "bg-muted/40",
                )}
                aria-expanded={isOpen}
                style={{ height: ROW_HEIGHT }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
          {paddingBottom > 0 && (
            <tr aria-hidden="true">
              <td colSpan={columns.length} style={{ height: paddingBottom }} />
            </tr>
          )}
          {rows.length === 0 && !isFetching && (
            <tr>
              <td
                colSpan={columns.length}
                className="p-6 text-center text-muted-fg"
              >
                No decisions match these filters.
              </td>
            </tr>
          )}
          {isFetching && (
            <tr aria-live="polite">
              <td
                colSpan={columns.length}
                className="p-3 text-center text-ops-xs text-muted-fg"
              >
                Loading…
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
