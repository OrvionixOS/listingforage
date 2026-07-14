import { useEffect, useState } from "react";
import { Loader2, Download, Images as ImagesIcon, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ListingResult } from "@/lib/types";
import { SectionCard, ImagesSection } from "@/components/listing-sections";
import { Button } from "@/components/ui/button";

function GalleryImage({ listingId, n, title }: { listingId: string; n: number; title: string }) {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    let alive = true;
    let made: string | undefined;
    api.galleryBlobUrl(listingId, n).then((u) => {
      made = u;
      if (alive) setUrl(u);
      else URL.revokeObjectURL(u);
    }).catch(() => {});
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [listingId, n]);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-secondary/30">
      <div className="relative aspect-square w-full">
        {url ? (
          <img src={url} alt={title} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <div className="grid h-full w-full place-items-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        )}
        <span className="absolute left-2 top-2 grid h-7 w-7 place-items-center rounded-md gradient-primary text-xs font-bold text-primary-foreground">{n}</span>
        {url && (
          <a href={url} download={`etsy-image-${String(n).padStart(2, "0")}.png`}
             className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-md bg-background/80 text-foreground backdrop-blur transition-colors hover:bg-background">
            <Download className="h-4 w-4" />
          </a>
        )}
      </div>
      <p className="truncate px-3 py-2 text-xs font-medium text-muted-foreground">{title}</p>
    </div>
  );
}

export function RenderedGallery({ listingId, result }: { listingId: string; result: ListingResult }) {
  const [rendered, setRendered] = useState(result.renderedImages);
  const [busy, setBusy] = useState(false);

  const rerender = async () => {
    setBusy(true);
    try {
      const { rendered: r } = await api.renderGallery(listingId);
      setRendered(r);
      toast.success("Listing images re-rendered.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Render failed");
    } finally {
      setBusy(false);
    }
  };

  const downloadAll = async () => {
    try {
      const blob = await api.galleryZip(listingId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "etsy-listing-images.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  };

  const hasImages = (rendered?.length ?? 0) > 0;

  return (
    <div className="space-y-5">
      <SectionCard
        title="Your 10 Etsy listing images"
        icon={ImagesIcon}
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={rerender} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Re-render
            </Button>
            {hasImages && (
              <Button size="sm" className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90" onClick={downloadAll}>
                <Download className="h-4 w-4" /> Download all
              </Button>
            )}
          </div>
        }
      >
        <p className="text-sm text-muted-foreground">
          Finished 2000×2000 images, built from your product photos and brand palette — ready to upload to Etsy.
        </p>
        {hasImages ? (
          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {rendered!.map((img) => (
              <GalleryImage key={img.n} listingId={listingId} n={img.n} title={img.title} />
            ))}
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No rendered images yet — click <span className="font-medium">Re-render</span> to build them from your product photos.
          </div>
        )}
      </SectionCard>

      <SectionCard title="The strategy behind each image" icon={ImagesIcon}>
        <p className="mb-4 text-sm text-muted-foreground">
          Each image is designed around a specific buyer-psychology goal. Use these as your art direction if you want to refine them.
        </p>
        <ImagesSection result={result} />
      </SectionCard>
    </div>
  );
}
