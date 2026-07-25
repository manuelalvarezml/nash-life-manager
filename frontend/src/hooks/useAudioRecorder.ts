import { useState, useRef, useCallback } from 'react';

export interface RecordingResult {
  blob: Blob;
  durationSeconds: number;
}

interface UseAudioRecorderReturn {
  isRecording: boolean;
  duration: number;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<RecordingResult>;
  error: string | null;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const durationRef = useRef(0);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/mp4';

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(1000);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setDuration(0);
      durationRef.current = 0;

      timerRef.current = window.setInterval(() => {
        setDuration((d) => {
          const next = d + 1;
          durationRef.current = next;
          return next;
        });
      }, 1000);
    } catch (err) {
      setError('No se pudo acceder al micrófono');
      throw err;
    }
  }, []);

  const stopRecording = useCallback((): Promise<RecordingResult> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder) {
        resolve({ blob: new Blob(), durationSeconds: 0 });
        return;
      }

      // Stop timer immediately
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      const seconds = durationRef.current;

      // Stop all tracks IMMEDIATELY to prevent more audio capture
      // This is critical - stops the microphone from recording more
      recorder.stream.getTracks().forEach((t) => t.stop());

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        setIsRecording(false);
        resolve({ blob, durationSeconds: seconds });
      };

      // Request any pending data before stopping
      if (recorder.state === 'recording') {
        recorder.requestData();
      }
      recorder.stop();
    });
  }, []);

  return { isRecording, duration, startRecording, stopRecording, error };
}
