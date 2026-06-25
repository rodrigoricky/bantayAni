import Skeleton from '@/components/common/Skeleton';

export default function ClaimsLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6 md:ml-64 mt-16">
      <Skeleton className="mb-2" width="40%" height="32px" />
      <Skeleton className="mb-8" width="60%" height="16px" />
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-4">
          <div className="bg-white border rounded-md p-6 space-y-4">
            <Skeleton width="50%" height="20px" />
            <Skeleton width="100%" height="40px" />
            <Skeleton width="100%" height="40px" />
            <Skeleton width="100%" height="40px" />
            <Skeleton width="100%" height="44px" />
          </div>
        </div>
        <div className="col-span-12 lg:col-span-8">
          <div className="bg-white border rounded-md p-12">
            <Skeleton className="mx-auto mb-4" width="200px" height="200px" rounded />
            <Skeleton className="mx-auto" width="60%" height="20px" />
          </div>
        </div>
      </div>
    </div>
  );
}