import { useState } from 'react';

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${r}s`;
}

interface AudioPlayerRowProps {
  src: string;
  recordedDurationS: number | null | undefined;
}

/**
 * Shows HTML5 audio + duration from metadata when server did not send duration_s.
 */
export function AudioPlayerRow({ src, recordedDurationS }: AudioPlayerRowProps) {
  const [metaDuration, setMetaDuration] = useState<number | null>(null);

  const effective =
    recordedDurationS != null && recordedDurationS > 0
      ? recordedDurationS
      : metaDuration != null && metaDuration > 0 && Number.isFinite(metaDuration)
        ? metaDuration
        : null;

  return (
    <div className="space-y-1">
      <audio
        controls
        className="w-full max-w-md h-9 opacity-90"
        src={src}
        preload="metadata"
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration;
          if (d && Number.isFinite(d)) setMetaDuration(d);
        }}
      >
        Tu navegador no reproduce audio embebido.
      </audio>
      <p className="text-xs text-[var(--nash-text-muted)]">
        <span className="text-[var(--nash-text)]">Duración del audio:</span>{' '}
        {effective != null ? formatDuration(effective) : 'No disponible'}
      </p>
    </div>
  );
}
