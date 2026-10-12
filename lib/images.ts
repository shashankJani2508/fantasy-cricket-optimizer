// Screenshots are shrunk in the browser before upload (Vercel caps a request at about 4.5 MB).
export async function compress(file: File, maxW = 1080, quality = 0.85): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, maxW / bmp.width);
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
    c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise<Blob>((res) => c.toBlob((b) => res(b ?? file), "image/jpeg", quality));
  } catch { return file; }
}

export async function screenshotForm(files: FileList) {
  const form = new FormData();
  for (const f of Array.from(files).slice(0, 15)) form.append("files", await compress(f), f.name.replace(/\.\w+$/, ".jpg"));
  return form;
}
