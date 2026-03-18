import { useState, useCallback, useEffect, useRef } from "react";

export interface UseAudioWaveformReturn {
  start: () => Promise<void>;
  stop: () => void;
  waveformData: Uint8Array | null;
  isActive: boolean;
  elapsedSeconds: number;
  error: string | null;
}

export function useAudioWaveform(): UseAudioWaveformReturn {
  const [isActive, setIsActive] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [waveformData, setWaveformData] = useState<Uint8Array | null>(null);
  const [error, setError] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isActiveRef = useRef(false);

  const cleanup = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    isActiveRef.current = false;
  }, []);

  const updateWaveform = useCallback(() => {
    if (!analyserRef.current || !isActiveRef.current) return;

    const analyser = analyserRef.current;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(dataArray);
    setWaveformData(dataArray);

    animationFrameRef.current = requestAnimationFrame(updateWaveform);
  }, []);

  const start = useCallback(async () => {
    setError(null);

    if (
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function"
    ) {
      setError("getUserMedia is not supported in this browser");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      isActiveRef.current = true;
      setIsActive(true);
      setElapsedSeconds(0);

      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);

      animationFrameRef.current = requestAnimationFrame(updateWaveform);
    } catch (err) {
      cleanup();
      const message =
        err instanceof Error ? err.message : "Microphone access denied";
      setError(message);
    }
  }, [cleanup, updateWaveform]);

  const stop = useCallback(() => {
    cleanup();
    setIsActive(false);
    setWaveformData(null);
  }, [cleanup]);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    start,
    stop,
    waveformData,
    isActive,
    elapsedSeconds,
    error,
  };
}
