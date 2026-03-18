import { useRef, useEffect } from "react";

export interface AudioWaveformProps {
  waveformData: Uint8Array | null;
  width?: number;
  height?: number;
  color?: string;
}

export default function AudioWaveform({
  waveformData,
  height = 48,
  color = "#3b82f6",
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        canvas.width = width;
        canvas.height = height;
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!waveformData || waveformData.length === 0) {
      // Draw flat line for silence / no data
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.moveTo(0, canvas.height / 2);
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
      return;
    }

    const bufferLength = waveformData.length;
    const sliceWidth = canvas.width / bufferLength;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;

    let x = 0;
    for (let i = 0; i < bufferLength; i++) {
      const v = waveformData[i] / 128.0;
      const y = (v * canvas.height) / 2;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      x += sliceWidth;
    }

    ctx.stroke();
  }, [waveformData, color, height]);

  return (
    <div ref={containerRef} className="w-full" style={{ height }}>
      <canvas
        ref={canvasRef}
        height={height}
        style={{ width: "100%", height }}
        data-testid="waveform-canvas"
      />
    </div>
  );
}
