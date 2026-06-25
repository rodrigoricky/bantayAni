'use client';

import { useRouter } from 'next/navigation';
import { FileText, Wheat, Download, ChevronRight } from 'lucide-react';

export default function QuickActionsCard() {
  const router = useRouter();

  const actions = [
    { label: 'Verify New Claim', icon: FileText, href: '/claims' },
    { label: 'View All Farms', icon: Wheat, href: '/farms' },
    { label: 'Download Reports', icon: Download, href: '/reports' },
  ];

  return (
    <div className="bg-white/95 backdrop-blur-md border border-gray-200 rounded-xl shadow-2xl p-5 h-auto">
      <h3 className="text-base font-semibold text-gray-900 mb-4">Quick Actions</h3>
      <div className="space-y-2">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.href}
              type="button"
              onClick={() => router.push(action.href)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 active:scale-95 transition-all rounded-lg focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <Icon className="w-5 h-5 text-gray-600" />
              <span>{action.label}</span>
              <ChevronRight className="w-4 h-4 ml-auto text-gray-400" aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </div>
  );
}