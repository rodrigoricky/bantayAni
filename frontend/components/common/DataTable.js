'use client';

import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';

const PAGE_SIZE = 20;

function SortIcon({ columnKey, sortKey, sortDir }) {
  if (sortKey !== columnKey) {
    return <ChevronsUpDown className="w-3.5 h-3.5 text-gray-300" />;
  }
  return sortDir === 'asc'
    ? <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
    : <ChevronDown className="w-3.5 h-3.5 text-gray-500" />;
}

export default function DataTable({
  title,
  columns = [],
  data = [],
  statusTabs,
  statusKey = 'status',
  emptyMessage = 'No records found',
  toolbar,
  pageSize = PAGE_SIZE,
}) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(0);

  const handleSort = (key) => {
    if (!key) return;
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setPage(0);
  };

  const filtered = useMemo(() => {
    if (!statusTabs || statusFilter === 'ALL') return data;
    return data.filter((row) => row[statusKey] === statusFilter);
  }, [data, statusFilter, statusKey, statusTabs]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const col = columns.find((c) => c.key === sortKey);
    const getValue = col?.sortValue || ((row) => row[sortKey]);
    return [...filtered].sort((a, b) => {
      const av = getValue(a);
      const bv = getValue(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDir === 'asc' ? av - bv : bv - av;
      }
      const as = String(av).toLowerCase();
      const bs = String(bv).toLowerCase();
      if (as < bs) return sortDir === 'asc' ? -1 : 1;
      if (as > bs) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortDir, columns]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paginated = sorted.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {(title || toolbar || statusTabs) && (
        <div className="px-5 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          {title && <h3 className="section-title">{title}</h3>}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            {statusTabs && (
              <div className="flex flex-wrap gap-1">
                {statusTabs.map((tab) => (
                  <button
                    key={tab.value}
                    type="button"
                    onClick={() => { setStatusFilter(tab.value); setPage(0); }}
                    className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                      statusFilter === tab.value
                        ? 'bg-gray-100 text-gray-900 border-gray-300'
                        : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {tab.label}
                    {tab.count != null && (
                      <span className="ml-1 text-gray-400">({tab.count})</span>
                    )}
                  </button>
                ))}
              </div>
            )}
            {toolbar}
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`text-left text-xs font-semibold text-gray-400 uppercase tracking-[0.06em] px-4 py-3 border-b border-gray-100 ${
                    col.align === 'right' ? 'text-right' : ''
                  }`}
                >
                  {col.sortable !== false ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col.key)}
                      className="inline-flex items-center gap-1 hover:text-gray-600 transition-colors"
                    >
                      {col.label}
                      <SortIcon columnKey={col.key} sortKey={sortKey} sortDir={sortDir} />
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-gray-500">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paginated.map((row, idx) => (
                <tr
                  key={row.id || idx}
                  className="border-b border-gray-100 hover:bg-gray-50 transition-colors duration-150"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-4 text-sm text-gray-700 ${
                        col.align === 'right' ? 'text-right' : ''
                      }`}
                    >
                      {col.render ? col.render(row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {sorted.length > pageSize && (
        <div className="border-t border-gray-100 px-5 py-3 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, sorted.length)} of {sorted.length}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="btn-secondary h-8 px-3 text-xs disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-xs text-gray-500">
              Page {page + 1} of {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
              className="btn-secondary h-8 px-3 text-xs disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}