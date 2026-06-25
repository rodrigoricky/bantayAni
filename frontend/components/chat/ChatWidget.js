'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { MessageCircle, Bot, X, Trash2 } from 'lucide-react';
import api from '@/lib/api';
import { getSatelliteViewDate } from '@/lib/satelliteView';
import { saveClaimPrefill } from '@/lib/claimPrefill';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

const STORAGE_KEY = 'bantay_ani_chat_history';
const HINT_KEY = 'bantayani_chat_hint_seen';

function downloadCsv(rows, filename = 'bantay_ani_claims.csv') {
  if (!rows?.length) return;
  const headers = ['claim_number', 'farmer_name', 'status', 'damage_percentage', 'damage_type', 'filed_date'];
  const csv = [headers.join(','), ...rows.map((r) => headers.map((h) => `"${r[h] ?? ''}"`).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ChatWidget({
  isOpen: controlledOpen,
  onOpenChange,
  messages: controlledMessages,
  onMessagesChange,
  onMessageSent,
  messageCount = 0,
  maxMessages = 10,
  limitMessage = '',
}) {
  const router = useRouter();
  const [internalOpen, setInternalOpen] = useState(false);
  const [internalMessages, setInternalMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPulse, setShowPulse] = useState(false);
  const scrollRef = useRef(null);
  const pollRef = useRef(null);
  const claimPollStartRef = useRef(null);

  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const messages = controlledMessages ?? internalMessages;
  const setMessages = onMessagesChange ?? setInternalMessages;
  const chatLimited = messageCount >= maxMessages;

  useEffect(() => {
    if (!localStorage.getItem(HINT_KEY)) {
      setShowPulse(true);
      localStorage.setItem(HINT_KEY, '1');
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading]);

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  const appendAssistantMessage = (reply, action, buttons = []) => {
    const aiMsg = {
      role: 'assistant',
      content: reply,
      timestamp: new Date().toISOString(),
      buttons: buttons?.length ? buttons : action?.type === 'navigate' ? [action.data] : [],
      action,
    };
    setMessages((prev) => [...prev, aiMsg]);
    if (action?.type === 'claim_progress' && action.data?.job_id) {
      startClaimPolling(action.data.job_id);
    }
  };

  const startClaimPolling = (jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    claimPollStartRef.current = Date.now();
    const CLAIM_TIMEOUT_MS = 45000;

    const poll = async () => {
      if (Date.now() - claimPollStartRef.current > CLAIM_TIMEOUT_MS) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        appendAssistantMessage(
          'Verification is taking longer than expected. Check the Cases page for your claim status.',
          null,
        );
        return;
      }

      try {
        const res = await api.get(`/satellite/scan-status/${jobId}`);
        const status = res.data?.data || {};
        const progress = typeof status.progress === 'number' ? status.progress : 0;
        const stepMessage = status.message || status.current_step || 'Processing';

        setMessages((prev) => prev.map((msg) => {
          if (msg.action?.type !== 'claim_progress' || msg.action?.data?.job_id !== jobId) return msg;
          return {
            ...msg,
            content: `${stepMessage}... ${progress}%`,
            action: {
              ...msg.action,
              data: {
                ...msg.action.data,
                progress,
                current_step: stepMessage,
                message: stepMessage,
              },
            },
          };
        }));

        if (status.status === 'completed' && status.result) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          const result = status.result;
          const sat = result.satellite_analysis || {};
          const damage = sat.damage_percentage ?? result.damage_percentage;
          const recommendation = result.recommendation
            || (result.status === 'APPROVED' ? 'APPROVE' : result.status === 'REJECTED' ? 'REJECT' : result.status === 'FLAGGED' ? 'FLAG' : 'FLAG');
          const damageText = damage != null ? `${Number(damage).toFixed(1)}%` : 'N/A';
          appendAssistantMessage(
            `${result.farmer_name}: ${damageText} damage. Recommendation: ${recommendation}.`,
            {
              type: 'claim_complete',
              data: {
                result: { ...result, recommendation },
                case_url: `/case/${result.claim_id}`,
              },
            },
          );
        } else if (status.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          appendAssistantMessage(
            status.message || status.error || 'Verification failed. Please try again from the Claims page.',
            null,
          );
        }
      } catch {
        clearInterval(pollRef.current);
        pollRef.current = null;
        appendAssistantMessage('Could not check verification status. Please try again.', null);
      }
    };

    poll();
    pollRef.current = setInterval(poll, 1500);
  };

  const sendChatMessage = async (text) => {
    if (!text || loading || chatLimited) return;
    onMessageSent?.();
    const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    try {
      const history = [...messages, userMsg].slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
        action: m.action,
      }));
      const response = await api.post('/chat', {
        message: text,
        conversation_history: history,
        satellite_date: getSatelliteViewDate(),
      });
      const { response: reply, action, buttons } = response.data.data;
      if (action?.type === 'export_csv') downloadCsv(action.data, action.filename);
      if (action?.type === 'claim_redirect' && action.data) {
        redirectToClaimsWithPrefill(action.data);
        appendAssistantMessage(reply, null, buttons);
      } else {
        appendAssistantMessage(reply, action, buttons);
      }
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: 'Sorry, I could not process that request. Please try again.',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    await sendChatMessage(text);
  };

  const redirectToClaimsWithPrefill = (data) => {
    if (!data?.rsbsa_number) return;
    saveClaimPrefill(data);
    setOpen(false);
    router.push('/claims?autostart=1');
  };

  const handleClaimConfirm = () => {
    const pending = [...messages].reverse().find(
      (m) => m.action?.type === 'claim_confirmation_prompt' && m.action?.data,
    );
    if (pending?.action?.data) {
      redirectToClaimsWithPrefill(pending.action.data);
    }
  };

  const handleClaimCancel = () => sendChatMessage('cancel');

  const handleAction = (path) => {
    if (path?.startsWith('/')) router.push(path);
  };

  const handleClear = () => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const panelClass = open
    ? 'fixed z-50 bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden md:bottom-8 md:right-8 md:w-[400px] md:h-[600px] inset-0 md:inset-auto p-0 pt-16 md:pt-0'
    : '';

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => { setOpen(true); setShowPulse(false); }}
          className={`fixed bottom-8 right-8 z-50 w-[60px] h-[60px] rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 transition-all flex items-center justify-center ${showPulse ? 'animate-pulse' : ''}`}
          aria-label="Open chat assistant"
        >
          <MessageCircle className="w-7 h-7" />
        </button>
      )}

      {open && (
        <div className={panelClass}>
          <div className="flex items-center justify-between px-4 py-3 bg-blue-600 text-white shrink-0">
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 shrink-0" />
                <span className="font-semibold text-sm">BantayAni Auto</span>
              </div>
              <span className={`text-xs mt-0.5 ${chatLimited ? 'text-red-200' : 'text-blue-100'}`}>
                {messageCount} / {maxMessages} messages used
              </span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button type="button" onClick={handleClear} className="p-1.5 hover:bg-blue-700 rounded-md" title="Clear conversation">
                <Trash2 className="w-4 h-4" />
              </button>
              <button type="button" onClick={() => setOpen(false)} className="p-1.5 hover:bg-blue-700 rounded-md" aria-label="Minimize chat">
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-4 bg-gray-50">
            {messages.map((msg, i) => (
              <div key={i} onClick={(e) => { const btn = e.target.closest('[data-action-path]'); if (btn) handleAction(btn.dataset.actionPath); }}>
                <ChatMessage
                  message={msg}
                  onClaimConfirm={handleClaimConfirm}
                  onClaimCancel={handleClaimCancel}
                />
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0.15s]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0.3s]" />
                </span>
                BantayAni Auto is typing...
              </div>
            )}
            {chatLimited && limitMessage && (
              <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {limitMessage}
              </p>
            )}
          </div>
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={loading || chatLimited}
          />
        </div>
      )}
    </>
  );
}