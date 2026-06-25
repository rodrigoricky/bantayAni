'use client';

import { useEffect, useState } from 'react';

const STAGES = [
  { at: 0, progress: 0, message: 'Locating farm parcel...' },
  { at: 2000, progress: 15, message: 'Locating farm parcel...' },
  { at: 10000, progress: 30, message: 'Retrieving pre-event satellite imagery...' },
  { at: 30000, progress: 60, message: 'Computing vegetation index...' },
  { at: 60000, progress: 85, message: 'Retrieving post-event imagery...' },
  { at: 90000, progress: 85, message: 'Analyzing damage patterns...' },
];

export default function VerificationProgressBar({ active, complete }) {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState(STAGES[0].message);
  const [fastFinish, setFastFinish] = useState(false);

  useEffect(() => {
    if (!active) {
      setProgress(0);
      setMessage(STAGES[0].message);
      setFastFinish(false);
      return undefined;
    }

    const start = Date.now();
    const timer = setInterval(() => {
      const elapsed = Date.now() - start;
      let stage = STAGES[0];
      for (const s of STAGES) {
        if (elapsed >= s.at) stage = s;
      }
      if (!complete) {
        setProgress(stage.progress);
        setMessage(stage.message);
      }
    }, 200);

    return () => clearInterval(timer);
  }, [active, complete]);

  useEffect(() => {
    if (complete && active) {
      setFastFinish(true);
      setProgress(100);
      setMessage('Generating assessment...');
    }
  }, [complete, active]);

  if (!active && progress === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <p className="text-sm font-medium text-gray-700">{message}</p>
      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-green-500 rounded-full"
          style={{
            width: `${progress}%`,
            transition: fastFinish
              ? 'width 0.3s ease'
              : progress <= 30
                ? 'width 10s linear'
                : progress <= 60
                  ? 'width 20s linear'
                  : 'width 30s linear',
          }}
        />
      </div>
      <p className="text-xs text-gray-500">
        Live satellite analysis via Google Earth Engine - this may take 30-90 seconds.
      </p>
    </div>
  );
}