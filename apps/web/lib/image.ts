/** Downscale + re-encode a photo client-side before upload. A real phone
 * photo is routinely 3-10MB -- straight through, that blew past both the
 * backend's upload size cap and the API client's 8s per-attempt timeout
 * (built for small JSON bodies, not multi-MB uploads), so the photo attach
 * silently failed while the SOS itself (a separate, tiny request) still
 * went through -- "SOS sent, no photo" with no visible reason why. Capping
 * the longest side at 1280px and re-encoding as JPEG q0.75 brings any real
 * photo down to a few hundred KB: fast enough to upload reliably, and a
 * smaller payload for the vision-LLM call downstream too. */
export async function compressImage(file: File, maxDim = 1280, quality = 0.75): Promise<File> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return file; // decode failed (e.g. an unsupported format) -- fall back to the original rather than block the upload

  const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * scale));
  const h = Math.max(1, Math.round(bitmap.height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.drawImage(bitmap, 0, 0, w, h);

  const blob: Blob | null = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  if (!blob) return file;
  return new File([blob], "sos-photo.jpg", { type: "image/jpeg" });
}
