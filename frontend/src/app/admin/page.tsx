"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { createProject, register, listProjects } from "@/lib/api";

export default function AdminPage() {
  const queryClient = useQueryClient();

  // Project creation
  const [projSlug, setProjSlug] = useState("");
  const [projName, setProjName] = useState("");
  const [projPath, setProjPath] = useState("");
  const [projDesc, setProjDesc] = useState("");
  const [projMsg, setProjMsg] = useState("");

  const createProjectMutation = useMutation({
    mutationFn: () =>
      createProject({
        slug: projSlug,
        name: projName,
        source_path: projPath,
        description: projDesc || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setProjSlug("");
      setProjName("");
      setProjPath("");
      setProjDesc("");
      setProjMsg("Project created!");
    },
    onError: (err) => {
      setProjMsg(`Error: ${err.message}`);
    },
  });

  // User creation
  const [newUser, setNewUser] = useState("");
  const [newPass, setNewPass] = useState("");
  const [userMsg, setUserMsg] = useState("");

  const registerMutation = useMutation({
    mutationFn: () => register(newUser, newPass),
    onSuccess: () => {
      setNewUser("");
      setNewPass("");
      setUserMsg("User created!");
    },
    onError: (err) => {
      setUserMsg(`Error: ${err.message}`);
    },
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-8 flex items-center gap-4">
        <Link href="/projects" className="text-gray-400 hover:text-white">
          &larr; Projects
        </Link>
        <h1 className="text-3xl font-bold">Admin</h1>
      </div>

      {/* Create project */}
      <section className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">Create Project</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createProjectMutation.mutate();
          }}
          className="space-y-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm text-gray-400">Slug</label>
              <input
                value={projSlug}
                onChange={(e) => setProjSlug(e.target.value)}
                placeholder="my-project"
                className="w-full rounded bg-gray-800 px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Name</label>
              <input
                value={projName}
                onChange={(e) => setProjName(e.target.value)}
                placeholder="My Project"
                className="w-full rounded bg-gray-800 px-3 py-2 text-sm"
                required
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Source Path (relative to media root)
            </label>
            <input
              value={projPath}
              onChange={(e) => setProjPath(e.target.value)}
              placeholder="family/2024"
              className="w-full rounded bg-gray-800 px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Description
            </label>
            <input
              value={projDesc}
              onChange={(e) => setProjDesc(e.target.value)}
              placeholder="Optional description"
              className="w-full rounded bg-gray-800 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={createProjectMutation.isPending}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Create Project
          </button>
          {projMsg && (
            <p className="text-sm text-gray-300">{projMsg}</p>
          )}
        </form>
      </section>

      {/* Create user */}
      <section className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">Create User</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            registerMutation.mutate();
          }}
          className="flex flex-wrap gap-3"
        >
          <input
            value={newUser}
            onChange={(e) => setNewUser(e.target.value)}
            placeholder="Username"
            className="rounded bg-gray-800 px-3 py-2 text-sm"
            required
          />
          <input
            type="password"
            value={newPass}
            onChange={(e) => setNewPass(e.target.value)}
            placeholder="Password"
            className="rounded bg-gray-800 px-3 py-2 text-sm"
            required
          />
          <button
            type="submit"
            disabled={registerMutation.isPending}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Create User
          </button>
          {userMsg && (
            <p className="text-sm text-gray-300">{userMsg}</p>
          )}
        </form>
      </section>

      {/* Existing projects */}
      <section>
        <h2 className="mb-4 text-xl font-semibold">Existing Projects</h2>
        {projects?.length ? (
          <div className="space-y-2">
            {projects.map((p) => (
              <div
                key={p.id}
                className="rounded bg-gray-900 p-3 text-sm"
              >
                <span className="font-medium">{p.name}</span>
                <span className="ml-2 text-gray-400">/{p.slug}</span>
                <span className="ml-2 text-gray-500">{p.source_path}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No projects yet.</p>
        )}
      </section>
    </div>
  );
}
