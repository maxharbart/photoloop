"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runSetup, setToken } from "@/lib/api";

export default function SetupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    username: "",
    password: "",
    project_name: "",
    project_slug: "",
    project_source_path: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function deriveSlug(name: string) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { access_token, project_slug } = await runSetup(form);
      setToken(access_token);
      router.replace(`/projects/${project_slug}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md">
        <h1 className="mb-2 text-3xl font-bold">Welcome to Photoloop</h1>
        <p className="mb-8 text-gray-400">Create your admin account and first project to get started.</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold uppercase tracking-wider text-gray-500">Admin account</legend>
            <div>
              <label className="mb-1 block text-sm text-gray-300">Username</label>
              <input
                required
                value={form.username}
                onChange={(e) => set("username", e.target.value)}
                className="w-full rounded bg-gray-800 px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-300">Password</label>
              <input
                required
                type="password"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                className="w-full rounded bg-gray-800 px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold uppercase tracking-wider text-gray-500">First project</legend>
            <div>
              <label className="mb-1 block text-sm text-gray-300">Project name</label>
              <input
                required
                value={form.project_name}
                onChange={(e) => {
                  set("project_name", e.target.value);
                  if (!form.project_slug || form.project_slug === deriveSlug(form.project_name)) {
                    set("project_slug", deriveSlug(e.target.value));
                  }
                }}
                className="w-full rounded bg-gray-800 px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-300">Slug</label>
              <input
                required
                value={form.project_slug}
                onChange={(e) => set("project_slug", e.target.value)}
                pattern="[a-z0-9-]+"
                title="Lowercase letters, numbers, and hyphens only"
                className="w-full rounded bg-gray-800 px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-300">Media source path</label>
              <input
                required
                value={form.project_source_path}
                onChange={(e) => set("project_source_path", e.target.value)}
                placeholder="photos/family"
                className="w-full rounded bg-gray-800 px-3 py-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">Relative path inside the mounted media directory.</p>
            </div>
          </fieldset>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-blue-600 py-2 font-medium hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Setting up..." : "Create and continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
