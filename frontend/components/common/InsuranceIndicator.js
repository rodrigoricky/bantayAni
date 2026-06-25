'use client';

import { BadgeCheck } from 'lucide-react';

export default function InsuranceIndicator({ isInsured, className = '' }) {
  if (isInsured === false) {
    return <span className={`text-xs text-gray-400 font-normal ml-1 ${className}`}>(Not Insured)</span>;
  }
  if (isInsured) {
    return (
      <BadgeCheck
        className={`w-3.5 h-3.5 text-blue-500 inline-block ml-1 align-middle ${className}`}
        title="Insured Farmer"
        aria-label="Insured Farmer"
      />
    );
  }
  return null;
}