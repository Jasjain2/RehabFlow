'use client';

import { useEffect, useRef, useState } from 'react';
import type { LandmarkPoint } from '@/lib/types';

// Downscale before sending: MediaPipe doesn't need full resolution, and smaller
// frames keep the WebSocket responsive.
const CAPTURE_WIDTH = 480;
const JPEG_QUALITY = 0.7;
const MIN_VISIBILITY = 0.5;

// MediaPipe BlazePose landmark pairs to draw (torso, arms, legs)
const POSE_CONNECTIONS: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
];

interface Props {
  intervalMs: number;
  /** Whether frames should be captured and sent */
  active: boolean;
  onFrame: (jpegDataUrl: string) => void;
  landmarks?: LandmarkPoint[] | null;
}

export default function CameraFeed({ intervalMs, active, onFrame, landmarks }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const onFrameRef = useRef(onFrame);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch((err: unknown) => {
        const denied = err instanceof DOMException && err.name === 'NotAllowedError';
        setError(denied ? 'Camera access was denied. Allow it in your browser settings.' : 'Could not open the camera.');
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    const canvas = document.createElement('canvas');
    const id = setInterval(() => {
      const video = videoRef.current;
      if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      canvas.width = CAPTURE_WIDTH;
      canvas.height = Math.round((video.videoHeight / video.videoWidth) * CAPTURE_WIDTH);
      canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
      onFrameRef.current(canvas.toDataURL('image/jpeg', JPEG_QUALITY));
    }, intervalMs);
    return () => clearInterval(id);
  }, [active, intervalMs]);

  useEffect(() => {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !video || !ctx) return;
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!landmarks) return;

    const visible = (i: number) => landmarks[i] && landmarks[i][2] >= MIN_VISIBILITY;
    const px = (i: number): [number, number] => [landmarks[i][0] * canvas.width, landmarks[i][1] * canvas.height];

    ctx.strokeStyle = '#2dd4bf';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    for (const [a, b] of POSE_CONNECTIONS) {
      if (!visible(a) || !visible(b)) continue;
      ctx.beginPath();
      ctx.moveTo(...px(a));
      ctx.lineTo(...px(b));
      ctx.stroke();
    }
    ctx.fillStyle = '#ffffff';
    for (const i of new Set(POSE_CONNECTIONS.flat())) {
      if (!visible(i)) continue;
      ctx.beginPath();
      ctx.arc(...px(i), 4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }, [landmarks]);

  if (error) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-lg bg-slate-900 p-6 text-center text-slate-200">
        {error}
      </div>
    );
  }

  // Mirrored so it behaves like a mirror; frames are captured unmirrored so the
  // backend sees the user's real left and right.
  return (
    <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-slate-900">
      <video ref={videoRef} autoPlay playsInline muted className="h-full w-full -scale-x-100 object-cover" />
      <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100" />
    </div>
  );
}
