import Image from 'next/image';
import LoadingSpinner from '@/components/common/LoadingSpinner';

export default function VerifyLoading() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
      <Image src="/logo.png" alt="Bantay Ani" width={180} height={44} className="h-11 w-auto object-contain mb-8" priority />
      <LoadingSpinner size="md" />
      <p className="mt-4 text-sm text-gray-500">Verifying report...</p>
    </div>
  );
}