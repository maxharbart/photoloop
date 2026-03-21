"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listProjects } from "@/lib/api";
import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

export default function ProjectsPage() {
  const router = useRouter();
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Projects</h1>
        <div className="flex gap-3">
          <Link
            href="/admin"
            className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700"
          >
            Admin
          </Link>
          <button
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700"
          >
            Sign out
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-400">Loading projects...</div>
      ) : !projects?.length ? (
        <div className="text-gray-400">
          No projects available. Ask an admin to create one and add you as a
          member.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.slug}`}
              className="rounded-lg bg-gray-900 p-6 transition hover:bg-gray-800"
            >
              <h2 className="text-lg font-semibold">{p.name}</h2>
              <p className="mt-1 text-sm text-gray-400">/{p.slug}</p>
              {p.description && (
                <p className="mt-2 text-sm text-gray-300">{p.description}</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
