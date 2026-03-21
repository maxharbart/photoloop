"use client";

import { useEffect, useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Photo, updatePhotoMetadata } from "@/lib/api";
import { format } from "date-fns";

interface LightboxProps {
  photos: Photo[];
  index: number;
  slug: string;
  onClose: () => void;
  onChange: (index: number) => void;
}

export function Lightbox({
  photos,
  index,
  slug,
  onClose,
  onChange,
}: LightboxProps) {
  const photo = photos[index];
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState(false);
  const [editDate, setEditDate] = useState("");
  const [editLat, setEditLat] = useState("");
  const [editLon, setEditLon] = useState("");

  const metadataMutation = useMutation({
    mutationFn: (data: {
      taken_at?: string;
      gps_lat?: number;
      gps_lon?: number;
    }) => updatePhotoMetadata(slug, photo.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["photos", slug] });
      setEditMode(false);
    },
  });

  const prev = useCallback(() => {
    if (index > 0) onChange(index - 1);
  }, [index, onChange]);

  const next = useCallback(() => {
    if (index < photos.length - 1) onChange(index + 1);
  }, [index, photos.length, onChange]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, prev, next]);

  useEffect(() => {
    setEditMode(false);
    setEditDate(photo.taken_at ? photo.taken_at.slice(0, 16) : "");
    setEditLat(photo.gps_lat?.toString() ?? "");
    setEditLon(photo.gps_lon?.toString() ?? "");
  }, [photo]);

  function handleSave() {
    const data: {
      taken_at?: string;
      gps_lat?: number;
      gps_lon?: number;
    } = {};
    if (editDate) data.taken_at = new Date(editDate).toISOString();
    if (editLat) data.gps_lat = parseFloat(editLat);
    if (editLon) data.gps_lon = parseFloat(editLon);
    metadataMutation.mutate(data);
  }

  return (
    <div className="fixed inset-0 z-50 flex bg-black/90">
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute right-4 top-4 z-10 text-2xl text-white/70 hover:text-white"
      >
        &times;
      </button>

      {/* Nav buttons */}
      {index > 0 && (
        <button
          onClick={prev}
          className="absolute left-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/50 px-3 py-2 text-xl text-white/70 hover:text-white"
        >
          &lsaquo;
        </button>
      )}
      {index < photos.length - 1 && (
        <button
          onClick={next}
          className="absolute right-80 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/50 px-3 py-2 text-xl text-white/70 hover:text-white"
        >
          &rsaquo;
        </button>
      )}

      {/* Image or Video */}
      <div className="flex flex-1 items-center justify-center p-8">
        {photo.media_type === "video" && photo.original_url ? (
          <video
            key={photo.id}
            src={photo.original_url}
            controls
            className="max-h-full max-w-full"
            preload="metadata"
          />
        ) : photo.thumb_md_url ? (
          <img
            src={photo.thumb_md_url}
            alt={photo.filename}
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <div className="text-gray-500">No preview available</div>
        )}
      </div>

      {/* Info panel */}
      <div className="w-80 overflow-y-auto border-l border-gray-800 bg-gray-900 p-6">
        <h2 className="mb-4 text-lg font-semibold">{photo.filename}</h2>

        <div className="space-y-3 text-sm">
          <div>
            <span className="text-gray-400">Date: </span>
            {photo.taken_at
              ? format(new Date(photo.taken_at), "PPpp")
              : "Unknown"}
            {photo.date_estimated && (
              <span className="ml-1 rounded bg-yellow-600/50 px-1 text-xs">
                estimated
              </span>
            )}
          </div>

          <div>
            <span className="text-gray-400">Size: </span>
            {photo.width} &times; {photo.height}
          </div>

          <div>
            <span className="text-gray-400">File size: </span>
            {(photo.file_size / 1024 / 1024).toFixed(1)} MB
          </div>

          {photo.media_type === "video" && photo.duration != null && (
            <div>
              <span className="text-gray-400">Duration: </span>
              {Math.floor(photo.duration / 60)}:{String(Math.floor(photo.duration % 60)).padStart(2, "0")}
            </div>
          )}

          {(photo.gps_lat !== null || photo.gps_lon !== null) && (
            <div>
              <span className="text-gray-400">GPS: </span>
              {photo.gps_lat?.toFixed(5)}, {photo.gps_lon?.toFixed(5)}
            </div>
          )}

          {photo.location_name && (
            <div>
              <span className="text-gray-400">Location: </span>
              {photo.location_name}
            </div>
          )}
        </div>

        {/* Edit metadata */}
        <div className="mt-6 border-t border-gray-800 pt-4">
          {editMode ? (
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Date/Time
                </label>
                <input
                  type="datetime-local"
                  value={editDate}
                  onChange={(e) => setEditDate(e.target.value)}
                  className="w-full rounded bg-gray-800 px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Latitude
                </label>
                <input
                  type="number"
                  step="any"
                  value={editLat}
                  onChange={(e) => setEditLat(e.target.value)}
                  className="w-full rounded bg-gray-800 px-2 py-1 text-sm"
                  placeholder="-90 to 90"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Longitude
                </label>
                <input
                  type="number"
                  step="any"
                  value={editLon}
                  onChange={(e) => setEditLon(e.target.value)}
                  className="w-full rounded bg-gray-800 px-2 py-1 text-sm"
                  placeholder="-180 to 180"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={metadataMutation.isPending}
                  className="rounded bg-blue-600 px-3 py-1 text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  className="rounded bg-gray-700 px-3 py-1 text-sm hover:bg-gray-600"
                >
                  Cancel
                </button>
              </div>
              {metadataMutation.isError && (
                <p className="text-xs text-red-400">
                  Failed to update metadata
                </p>
              )}
            </div>
          ) : (
            <button
              onClick={() => setEditMode(true)}
              className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700"
            >
              Edit metadata
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
