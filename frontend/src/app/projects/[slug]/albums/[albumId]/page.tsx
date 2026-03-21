"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getAlbum,
  listPhotos,
  addPhotosToAlbum,
  removePhotoFromAlbum,
  reorderAlbumPhotos,
  type Photo,
} from "@/lib/api";
import { Lightbox } from "@/components/Lightbox";

export default function AlbumDetailPage() {
  const { slug, albumId } = useParams<{ slug: string; albumId: string }>();
  const queryClient = useQueryClient();
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [showAddPhotos, setShowAddPhotos] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: album, isLoading } = useQuery({
    queryKey: ["album", slug, albumId],
    queryFn: () => getAlbum(slug, albumId),
  });

  // All project photos for "add to album" modal
  const { data: allPhotos } = useQuery({
    queryKey: ["photos", slug, "all"],
    queryFn: () => listPhotos(slug, { page_size: 100 }),
    enabled: showAddPhotos,
  });

  const addMutation = useMutation({
    mutationFn: (ids: string[]) => addPhotosToAlbum(slug, albumId, ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["album", slug, albumId] });
      setShowAddPhotos(false);
      setSelectedIds(new Set());
    },
  });

  const removeMutation = useMutation({
    mutationFn: (photoId: string) =>
      removePhotoFromAlbum(slug, albumId, photoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["album", slug, albumId] });
    },
  });

  const photos = album?.photos ?? [];

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Link
          href={`/projects/${slug}/albums`}
          className="text-gray-400 hover:text-white"
        >
          &larr; Albums
        </Link>
        <h1 className="text-2xl font-bold">{album?.name ?? "Album"}</h1>
        {album?.description && (
          <p className="text-sm text-gray-400">{album.description}</p>
        )}
        <div className="flex-1" />
        <button
          onClick={() => setShowAddPhotos(true)}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium hover:bg-blue-700"
        >
          Add photos
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-400">Loading...</div>
      ) : !photos.length ? (
        <div className="text-gray-400">
          No photos in this album. Add some!
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {photos.map((photo, i) => (
            <div key={photo.id} className="group relative">
              <button
                onClick={() => setLightboxIndex(i)}
                className="aspect-square w-full overflow-hidden rounded bg-gray-900"
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
                    No thumb
                  </div>
                )}
              </button>
              <button
                onClick={() => {
                  if (confirm("Remove from album?")) {
                    removeMutation.mutate(photo.id);
                  }
                }}
                className="absolute right-1 top-1 hidden rounded bg-red-900/80 px-1.5 py-0.5 text-xs text-red-200 group-hover:block"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add photos modal */}
      {showAddPhotos && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-y-auto rounded-lg bg-gray-900 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Add photos to album</h2>
              <button
                onClick={() => setShowAddPhotos(false)}
                className="text-gray-400 hover:text-white"
              >
                &times;
              </button>
            </div>

            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
              {allPhotos?.items.map((photo) => (
                <button
                  key={photo.id}
                  onClick={() => toggleSelect(photo.id)}
                  className={`aspect-square overflow-hidden rounded border-2 ${
                    selectedIds.has(photo.id)
                      ? "border-blue-500"
                      : "border-transparent"
                  }`}
                >
                  {photo.thumb_sm_url ? (
                    <img
                      src={photo.thumb_sm_url}
                      alt={photo.filename}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center bg-gray-800 text-xs text-gray-600">
                      ?
                    </div>
                  )}
                </button>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={() => addMutation.mutate(Array.from(selectedIds))}
                disabled={selectedIds.size === 0 || addMutation.isPending}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                Add {selectedIds.size} photo{selectedIds.size !== 1 ? "s" : ""}
              </button>
              <button
                onClick={() => setShowAddPhotos(false)}
                className="rounded bg-gray-700 px-4 py-2 text-sm hover:bg-gray-600"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && photos.length > 0 && (
        <Lightbox
          photos={photos}
          index={lightboxIndex}
          slug={slug}
          onClose={() => setLightboxIndex(null)}
          onChange={setLightboxIndex}
        />
      )}
    </div>
  );
}
