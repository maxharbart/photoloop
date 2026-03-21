"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getProject,
  listPhotos,
  listAlbums,
  triggerScan,
  type Photo,
} from "@/lib/api";
import { Lightbox } from "@/components/Lightbox";

export default function GalleryPage() {
  const { slug } = useParams<{ slug: string }>();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<"asc" | "desc">("asc");
  const [albumFilter, setAlbumFilter] = useState<string>("");
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const { data: project } = useQuery({
    queryKey: ["project", slug],
    queryFn: () => getProject(slug),
  });

  const { data: photos, isLoading } = useQuery({
    queryKey: ["photos", slug, page, sort, albumFilter],
    queryFn: () =>
      listPhotos(slug, {
        page,
        page_size: 48,
        sort,
        album_id: albumFilter || undefined,
      }),
  });

  const { data: albums } = useQuery({
    queryKey: ["albums", slug],
    queryFn: () => listAlbums(slug),
  });

  const scanMutation = useMutation({
    mutationFn: () => triggerScan(slug),
    onSuccess: () => {
      alert("Scan started. Photos will appear as they are processed.");
    },
  });

  const totalPages = photos ? Math.ceil(photos.total / photos.page_size) : 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Top bar */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Link href="/projects" className="text-gray-400 hover:text-white">
          &larr; Projects
        </Link>
        <h1 className="text-2xl font-bold">{project?.name ?? slug}</h1>
        <div className="flex-1" />

        {/* Album filter */}
        <select
          value={albumFilter}
          onChange={(e) => {
            setAlbumFilter(e.target.value);
            setPage(1);
          }}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm"
        >
          <option value="">All photos</option>
          {albums?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>

        {/* Sort */}
        <button
          onClick={() => setSort(sort === "asc" ? "desc" : "asc")}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700"
        >
          {sort === "asc" ? "Oldest first" : "Newest first"}
        </button>

        {/* Scan */}
        <button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {scanMutation.isPending ? "Starting..." : "Scan"}
        </button>

        {/* Albums link */}
        <Link
          href={`/projects/${slug}/albums`}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700"
        >
          Albums
        </Link>
      </div>

      {/* Photo grid */}
      {isLoading ? (
        <div className="text-gray-400">Loading photos...</div>
      ) : !photos?.items.length ? (
        <div className="text-gray-400">
          No photos found. Try scanning the source folder.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {photos.items.map((photo, i) => (
              <button
                key={photo.id}
                onClick={() => setLightboxIndex(i)}
                className="group relative aspect-square overflow-hidden rounded bg-gray-900"
              >
                {photo.thumb_sm_url ? (
                  <img
                    src={photo.thumb_sm_url}
                    alt={photo.filename}
                    className="h-full w-full object-cover transition group-hover:scale-105"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-gray-600">
                    No thumbnail
                  </div>
                )}
                {photo.media_type === "video" && (
                  <>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <svg
                        className="h-10 w-10 text-white/80 drop-shadow-lg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                    {photo.duration != null && (
                      <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-white">
                        {Math.floor(photo.duration / 60)}:{String(Math.floor(photo.duration % 60)).padStart(2, "0")}
                      </span>
                    )}
                  </>
                )}
                {photo.date_estimated && (
                  <span className="absolute left-1 top-1 rounded bg-yellow-600/80 px-1 text-[10px]">
                    date estimated
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded bg-gray-800 px-3 py-1 text-sm disabled:opacity-40"
              >
                Prev
              </button>
              <span className="text-sm text-gray-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="rounded bg-gray-800 px-3 py-1 text-sm disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && photos?.items && (
        <Lightbox
          photos={photos.items}
          index={lightboxIndex}
          slug={slug}
          onClose={() => setLightboxIndex(null)}
          onChange={setLightboxIndex}
        />
      )}
    </div>
  );
}
