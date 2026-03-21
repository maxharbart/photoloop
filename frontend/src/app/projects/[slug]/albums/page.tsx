"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  listAlbums,
  createAlbum,
  deleteAlbum,
  getProject,
} from "@/lib/api";

export default function AlbumsPage() {
  const { slug } = useParams<{ slug: string }>();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: project } = useQuery({
    queryKey: ["project", slug],
    queryFn: () => getProject(slug),
  });

  const { data: albums, isLoading } = useQuery({
    queryKey: ["albums", slug],
    queryFn: () => listAlbums(slug),
  });

  const createMutation = useMutation({
    mutationFn: () => createAlbum(slug, { name, description: description || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["albums", slug] });
      setName("");
      setDescription("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (albumId: string) => deleteAlbum(slug, albumId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["albums", slug] });
    },
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-6 flex items-center gap-4">
        <Link
          href={`/projects/${slug}`}
          className="text-gray-400 hover:text-white"
        >
          &larr; {project?.name ?? slug}
        </Link>
        <h1 className="text-2xl font-bold">Albums</h1>
      </div>

      {/* Create album */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createMutation.mutate();
        }}
        className="mb-8 flex flex-wrap gap-3"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Album name"
          className="rounded bg-gray-800 px-3 py-2 text-sm"
          required
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          className="rounded bg-gray-800 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          Create
        </button>
      </form>

      {/* Album list */}
      {isLoading ? (
        <div className="text-gray-400">Loading...</div>
      ) : !albums?.length ? (
        <div className="text-gray-400">No albums yet.</div>
      ) : (
        <div className="space-y-2">
          {albums.map((album) => (
            <div
              key={album.id}
              className="flex items-center justify-between rounded-lg bg-gray-900 p-4"
            >
              <Link
                href={`/projects/${slug}/albums/${album.id}`}
                className="hover:text-blue-400"
              >
                <h3 className="font-medium">{album.name}</h3>
                {album.description && (
                  <p className="text-sm text-gray-400">{album.description}</p>
                )}
                {album.photo_count !== undefined && (
                  <p className="text-xs text-gray-500">
                    {album.photo_count} photos
                  </p>
                )}
              </Link>
              <button
                onClick={() => {
                  if (confirm("Delete this album?")) {
                    deleteMutation.mutate(album.id);
                  }
                }}
                className="rounded bg-red-900/50 px-3 py-1 text-sm text-red-300 hover:bg-red-900"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
