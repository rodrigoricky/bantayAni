import Skeleton from '@/components/common/Skeleton';

export default function DashboardLoading() {
  return (
    <div className="w-full h-full bg-gray-100 animate-shimmer relative">
      <div className="absolute top-6 left-6 z-30">
        <div className="bg-white border border-gray-200 rounded-xl p-4 w-[200px]">
          <Skeleton className="mb-3" width="60%" height="12px" />
          <Skeleton className="mb-2" width="100%" height="16px" />
          <Skeleton className="mb-2" width="100%" height="16px" />
          <Skeleton width="100%" height="16px" />
        </div>
      </div>
      <div className="absolute bottom-6 left-6 z-30">
        <div className="bg-white border border-gray-200 rounded-xl p-4 w-[280px]">
          <Skeleton className="mb-3" width="50%" height="14px" />
          <Skeleton className="mb-2" width="100%" height="6px" />
          <Skeleton width="100%" height="40px" />
        </div>
      </div>
    </div>
  );
}