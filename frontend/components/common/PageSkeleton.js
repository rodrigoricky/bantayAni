export function PageHeaderSkeleton({ subtitle = true }) {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded-lg w-48" />
      {subtitle && <div className="h-4 bg-gray-100 rounded w-72 mt-2" />}
    </div>
  );
}

export function StatCardsSkeleton({ count = 4, cols = 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4' }) {
  return (
    <div className={`grid ${cols} gap-6 animate-pulse`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="h-3 bg-gray-100 rounded w-24" />
          <div className="h-8 bg-gray-200 rounded w-16 mt-3" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 8 }) {
  return (
    <div className="card-base overflow-hidden animate-pulse">
      <div className="px-5 py-4 border-b border-gray-200">
        <div className="h-5 bg-gray-200 rounded w-40" />
      </div>
      <div className="px-5 py-3 border-b border-gray-200 flex gap-3">
        <div className="h-8 bg-gray-100 rounded-lg flex-1 max-w-xs" />
        <div className="h-8 bg-gray-100 rounded-lg w-32" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="px-5 py-4 flex items-center gap-4">
            <div className="h-8 w-8 bg-gray-100 rounded-full flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-1/3" />
              <div className="h-3 bg-gray-100 rounded w-1/4" />
            </div>
            <div className="h-4 bg-gray-100 rounded w-16" />
            <div className="h-6 bg-gray-100 rounded-full w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function CardListSkeleton({ count = 4 }) {
  return (
    <div className="space-y-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-gray-100 bg-white p-5">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 bg-gray-100 rounded-lg flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-2/3" />
              <div className="h-3 bg-gray-100 rounded w-full" />
              <div className="h-3 bg-gray-100 rounded w-4/5" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function MapPageSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-pulse">
      <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 h-[480px]">
        <div className="w-full h-full bg-gray-200 rounded-2xl" />
      </div>
      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="h-5 bg-gray-200 rounded w-40" />
          <div className="h-3 bg-gray-100 rounded w-28 mt-2" />
        </div>
        <div className="p-5 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ListPageSkeleton({ statCount = 4, tableRows = 8 }) {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <StatCardsSkeleton count={statCount} />
      <TableSkeleton rows={tableRows} />
    </div>
  );
}