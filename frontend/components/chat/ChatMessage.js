'use client';

import Link from 'next/link';
import { Bot, User } from 'lucide-react';
import ChatMarkdown from './ChatMarkdown';

const STATUS_COLORS = {
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  FLAGGED: 'bg-amber-100 text-amber-800',
  PENDING: 'bg-gray-100 text-gray-800',
};

function ClaimConfirmationCard({ data, onConfirm, onCancel }) {
  if (!data) return null;
  return (
    <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs space-y-2">
      <p className="font-semibold text-gray-900">{data.farmer_name}</p>
      <p className="text-gray-600">RSBSA: <span className="font-mono">{data.rsbsa_number}</span></p>
      <p className="text-gray-600">{data.crop_type} · {data.area_hectares} ha</p>
      <p className="text-gray-500">Disaster: Oct 23, 2024 · Flood</p>
      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={onConfirm}
          className="flex-1 px-3 py-2 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg"
        >
          Confirm
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-2 text-xs font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function ClaimProgressCard({ data }) {
  if (!data) return null;
  const percent = data.progress ?? 0;
  return (
    <div className="mt-3 space-y-2">
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-green-600 rounded-full transition-all duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-xs text-gray-500">
        {(data.message || data.current_step || 'Processing')}... {percent}%
      </p>
    </div>
  );
}

function ClaimCompleteCard({ data }) {
  if (!data) return null;
  const result = data.result || {};
  const sat = result.satellite_analysis || {};
  const damage = sat.damage_percentage ?? result.damage_percentage;
  const recommendation = result.recommendation || result.status;
  return (
    <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs space-y-2">
      <p className="font-semibold text-gray-900">{result.farmer_name}</p>
      <p className="text-gray-700">
        Damage: {damage != null ? `${Number(damage).toFixed(1)}%` : 'N/A'}
      </p>
      <p className="text-gray-700 font-medium">
        Recommendation: {recommendation}
      </p>
      {data.case_url && (
        <Link
          href={data.case_url}
          className="inline-block mt-1 px-3 py-2 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg"
        >
          View full analysis
        </Link>
      )}
    </div>
  );
}

export default function ChatMessage({ message, onClaimConfirm, onClaimCancel }) {
  const isUser = message.role === 'user';
  const time = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';
  const action = message.action;

  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
          isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
        }`}
      >
        {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
      </div>

      <div className={`flex flex-col max-w-[88%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-md'
              : 'bg-white text-gray-900 rounded-bl-md border border-gray-200 shadow-sm'
          }`}
        >
          {isUser ? (
            <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
          ) : (
            <ChatMarkdown content={message.content} />
          )}

          {action?.type === 'claim_confirmation_prompt' && (
            <ClaimConfirmationCard
              data={action.data}
              onConfirm={onClaimConfirm}
              onCancel={onClaimCancel}
            />
          )}

          {action?.type === 'claim_progress' && (
            <ClaimProgressCard data={action.data} />
          )}

          {action?.type === 'claim_complete' && (
            <ClaimCompleteCard data={action.data} />
          )}

          {message.buttons?.length > 0 && (
            <div className="mt-3 space-y-1.5 pt-2 border-t border-gray-200/60">
              {message.buttons.map((btn) => (
                <button
                  key={btn.path}
                  type="button"
                  data-action-path={btn.path}
                  className="block w-full text-left px-3 py-2 text-xs font-medium bg-white text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  {btn.label}
                </button>
              ))}
            </div>
          )}
        </div>
        {time && (
          <span className="text-[10px] text-gray-400 mt-1 px-1">{time}</span>
        )}
      </div>
    </div>
  );
}