/**
 * Exportação de cena do gêmeo 3D (17f.9) — PNG e frames de tour.
 */

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error('Falha ao gerar PNG da cena'));
        else resolve(blob);
      },
      'image/png',
      0.95,
    );
  });
}

/** Captura o canvas MapLibre (requer preserveDrawingBuffer: true). */
export async function exportMapLibrePng(
  map: { getCanvas: () => HTMLCanvasElement; triggerRepaint?: () => void },
  filename = `sinidu-cena-${Date.now()}.png`,
): Promise<void> {
  map.triggerRepaint?.();
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const canvas = map.getCanvas();
  const blob = await canvasToPngBlob(canvas);
  downloadBlob(blob, filename);
}

/**
 * Grava um trecho curto do canvas como WebM (quando o browser permitir).
 * Retorna false se MediaRecorder/WebM não estiver disponível.
 */
export async function exportMapLibreWebm(
  map: { getCanvas: () => HTMLCanvasElement },
  durationMs = 4000,
  filename = `sinidu-tour-${Date.now()}.webm`,
): Promise<boolean> {
  const canvas = map.getCanvas();
  if (typeof MediaRecorder === 'undefined' || !canvas.captureStream) {
    return false;
  }
  const stream = canvas.captureStream(24);
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9'
    : MediaRecorder.isTypeSupported('video/webm')
      ? 'video/webm'
      : '';
  if (!mime) return false;

  const chunks: BlobPart[] = [];
  const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 2_500_000 });
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const done = new Promise<Blob>((resolve) => {
    recorder.onstop = () => resolve(new Blob(chunks, { type: 'video/webm' }));
  });

  recorder.start(200);
  await new Promise((r) => setTimeout(r, durationMs));
  recorder.stop();
  stream.getTracks().forEach((t) => t.stop());
  const blob = await done;
  downloadBlob(blob, filename);
  return true;
}
