const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function setToken(token: string) {
  document.cookie = `token=${encodeURIComponent(token)}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
}

export function clearToken() {
  document.cookie = "token=; path=/; max-age=0";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const form = new FormData();
  form.append("username", username);
  form.append("password", password);
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: form,
  });
}

export interface UserOut {
  id: string;
  username: string;
  is_superuser: boolean;
  created_at: string;
}

export async function register(
  username: string,
  password: string,
): Promise<UserOut> {
  return request<UserOut>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

// Projects
export interface Project {
  id: string;
  slug: string;
  name: string;
  source_path: string;
  description: string | null;
  created_at: string;
}

export async function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export async function getProject(slug: string): Promise<Project> {
  return request<Project>(`/projects/${slug}`);
}

export async function createProject(data: {
  slug: string;
  name: string;
  source_path: string;
  description?: string;
}): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProject(
  slug: string,
  data: { name?: string; description?: string; source_path?: string },
): Promise<Project> {
  return request<Project>(`/projects/${slug}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export interface Member {
  user_id: string;
  username: string;
  role: string;
}

export async function addMember(
  slug: string,
  userId: string,
  role: string,
): Promise<void> {
  return request(`/projects/${slug}/members`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export async function removeMember(
  slug: string,
  userId: string,
): Promise<void> {
  return request(`/projects/${slug}/members/${userId}`, {
    method: "DELETE",
  });
}

// Photos
export interface Photo {
  id: string;
  project_id: string;
  relative_path: string;
  filename: string;
  taken_at: string;
  date_estimated: boolean;
  gps_lat: number | null;
  gps_lon: number | null;
  location_name: string | null;
  width: number;
  height: number;
  file_size: number;
  media_type: string;
  duration: number | null;
  thumb_sm_url: string | null;
  thumb_md_url: string | null;
  original_url: string | null;
  indexed_at: string;
}

export interface PhotoListResponse {
  items: Photo[];
  total: number;
  page: number;
  page_size: number;
}

export async function listPhotos(
  slug: string,
  params: {
    page?: number;
    page_size?: number;
    sort?: "asc" | "desc";
    album_id?: string;
  } = {},
): Promise<PhotoListResponse> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  if (params.sort) q.set("sort", params.sort);
  if (params.album_id) q.set("album_id", params.album_id);
  const qs = q.toString();
  return request<PhotoListResponse>(
    `/projects/${slug}/photos${qs ? `?${qs}` : ""}`,
  );
}

export async function getPhoto(
  slug: string,
  photoId: string,
): Promise<Photo> {
  return request<Photo>(`/projects/${slug}/photos/${photoId}`);
}

export async function triggerScan(
  slug: string,
): Promise<{ task_id: string }> {
  return request<{ task_id: string }>(`/projects/${slug}/scan`, {
    method: "POST",
  });
}

export async function getScanStatus(
  slug: string,
  taskId: string,
): Promise<{ status: string; result?: unknown }> {
  return request(`/projects/${slug}/scan/${taskId}`);
}

// Albums
export interface Album {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  cover_photo_id: string | null;
  created_at: string;
  photo_count?: number;
}

export async function listAlbums(slug: string): Promise<Album[]> {
  return request<Album[]>(`/projects/${slug}/albums`);
}

export async function getAlbum(
  slug: string,
  albumId: string,
): Promise<Album & { photos: Photo[] }> {
  return request(`/projects/${slug}/albums/${albumId}`);
}

export async function createAlbum(
  slug: string,
  data: { name: string; description?: string },
): Promise<Album> {
  return request<Album>(`/projects/${slug}/albums`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAlbum(
  slug: string,
  albumId: string,
  data: { name?: string; description?: string; cover_photo_id?: string },
): Promise<Album> {
  return request<Album>(`/projects/${slug}/albums/${albumId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAlbum(
  slug: string,
  albumId: string,
): Promise<void> {
  return request(`/projects/${slug}/albums/${albumId}`, {
    method: "DELETE",
  });
}

export async function addPhotosToAlbum(
  slug: string,
  albumId: string,
  photoIds: string[],
): Promise<void> {
  return request(`/projects/${slug}/albums/${albumId}/photos`, {
    method: "POST",
    body: JSON.stringify({ photo_ids: photoIds }),
  });
}

export async function removePhotoFromAlbum(
  slug: string,
  albumId: string,
  photoId: string,
): Promise<void> {
  return request(`/projects/${slug}/albums/${albumId}/photos/${photoId}`, {
    method: "DELETE",
  });
}

export async function reorderAlbumPhotos(
  slug: string,
  albumId: string,
  photoIds: string[],
): Promise<void> {
  return request(`/projects/${slug}/albums/${albumId}/photos/order`, {
    method: "PUT",
    body: JSON.stringify({ photo_ids: photoIds }),
  });
}

// Metadata
export async function updatePhotoMetadata(
  slug: string,
  photoId: string,
  data: { taken_at?: string; gps_lat?: number; gps_lon?: number },
): Promise<Photo> {
  return request<Photo>(`/projects/${slug}/photos/${photoId}/metadata`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export { ApiError };
