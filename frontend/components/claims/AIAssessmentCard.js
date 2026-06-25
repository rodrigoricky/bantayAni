'use client';

import { Circle } from 'lucide-react';
import { buildAiAssessmentSections, parseBoldSegments } from '@/lib/formatAiAssessment';

function BoldText({ text, className = '' }) {
  const segments = parseBoldSegments(text);
  return (
    <span className={className}>
      {segments.map((seg, i) => (
        seg.type === 'bold'
          ? <strong key={i} className="font-semibold text-gray-900">{seg.text}</strong>
          : <span key={i}>{seg.text}</span>
      ))}
    </span>
  );
}

export default function AIAssessmentCard({ result }) {
  const { primaryFinding, indicators, conclusion } = buildAiAssessmentSections(result);

  return (
    <div className="card-base overflow-hidden">
      <div className="px-6 pt-6">
        <h3 className="card-section-header">AI Assessment</h3>
      </div>
      <div className="mx-6 border-t border-gray-100" />
      <div className="px-6 py-6 space-y-5 text-sm text-gray-700 leading-relaxed">
        <div>
          <p className="text-[13px] font-medium text-gray-500 mb-2">Primary Finding</p>
          <p className="text-[15px] leading-relaxed"><BoldText text={primaryFinding} /></p>
        </div>

        {indicators.length > 0 && (
          <div>
            <p className="text-[13px] font-medium text-gray-500 mb-2">Key Indicators</p>
            <ul className="space-y-2">
              {indicators.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-[15px]">
                  <Circle className="w-1.5 h-1.5 mt-2 shrink-0 fill-gray-300 text-gray-300" aria-hidden="true" />
                  <span><BoldText text={item} /></span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <p className="text-[13px] font-medium text-gray-500 mb-2">Conclusion</p>
          <p className="text-[15px] leading-relaxed"><BoldText text={conclusion} /></p>
        </div>
      </div>
    </div>
  );
}