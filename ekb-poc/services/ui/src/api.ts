/** API client. Local auth: the signed-in username travels as X-User (Keycloak/OIDC in production). */

export interface User {
  username: string;
  display_name: string;
  roles: string[];
  access_groups: string[];
}

export interface Citation {
  n: number;
  chunk_id: string;
  doc_id: string;
  version_id: string;
  version_no: number;
  title: string;
  page: number;
  heading_path: string;
  snippet: string;
  origin: "hybrid" | "graph";
  via: string[];
}

export interface Retrieved {
  chunk_id: string;
  title: string;
  version_no: number;
  page: number;
  heading_path: string;
  origin: "hybrid" | "graph";
  score?: number;
  ranks?: { bm25?: number; knn?: number };
  via?: string[];
  access_group: string;
}

export interface DataResult {
  sql: string | null;
  executed_sql: string | null;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  row_count: number;
  truncated: boolean;
  chart: { type?: string; x?: string | null; y?: string | null };
  attempts: number;
  error: string | null;
  blocked: boolean;
}

export interface QueryResponse {
  trace_id: string;
  answer: string;
  citations: Citation[];
  route: "document" | "data" | "mixed";
  route_reason?: string;
  mode: string;
  sql: string | null;
  data: DataResult | null;
  graph: { entities: { name: string; type: string }[]; relations: { source: string; rel: string; target: string }[] };
  retrieved: Retrieved[];
  latency_ms: number;
  timings: Record<string, number>;
  model: string;
}

export interface Version {
  version_id: string;
  version_no: number;
  status: string;
  is_active: boolean;
  effective_date: string;
  expiry_date: string | null;
  pipeline_status: string | null;
  pipeline_error: string | null;
  page_count: number | null;
  chunk_count: number | null;
  uploaded_by: string;
  created_at: string;
  file_name: string;
  summary: string | null;
}

export interface DocumentRow {
  doc_id: string;
  title: string;
  country: string;
  business_unit: string;
  category: string;
  product: string | null;
  access_group: string;
  owner_user: string;
  versions: Version[];
}

export interface Conflict {
  exact_duplicate: boolean;
  threshold: number;
  near_duplicates: { doc_id: string; version_id: string; title: string; version_no: number; similarity: number; text_overlap?: number; semantic?: number; flag: string }[];
}

export interface Task {
  task_id: string;
  step: "VERIFY" | "APPROVE" | "ACKNOWLEDGE";
  role: string;
  batch_id: string | null;
  created_at: string;
  version_id: string;
  version_no: number;
  file_name: string;
  effective_date: string;
  expiry_date: string | null;
  conflict: Conflict | null;
  uploaded_by: string;
  status: string;
  uploaded_at: string;
  doc_id: string;
  title: string;
  country: string;
  business_unit: string;
  category: string;
  product: string | null;
  access_group: string;
  self_upload: boolean;
}

export interface BrowseDoc {
  version_id: string;
  doc_id: string;
  title: string;
  version_no: number;
  category: string;
  product: string | null;
  business_unit: string;
  access_group: string;
  effective_date: string;
  expiry_date: string | null;
  matches: number;
  summary: string | null;
  key_info: Record<string, string>;
  sample_qa: { question: string; answer: string }[];
  entities: { name: string; type: string }[];
}

export interface Facet {
  value: string;
  count: number;
}

export interface Stats {
  active: number;
  in_review: number;
  indexing: number;
  superseded: number;
  pending_tasks: number;
  indexed_chunks: number;
  graph_entities: number;
}

export interface AuditRow {
  audit_id: number;
  ts: string;
  actor: string;
  action: string;
  object_ref: string | null;
  details: Record<string, unknown>;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

const USER_KEY = "ekb-user";

export function storedUser(): string | null {
  try {
    return localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}

export function storeUser(username: string | null) {
  try {
    if (username) localStorage.setItem(USER_KEY, username);
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* private mode â€” session just won't persist */
  }
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const user = storedUser();
  if (user) headers["X-User"] = user;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (!res.ok) {
    let detail: unknown = await res.text();
    try {
      detail = JSON.parse(detail as string).detail;
    } catch {
      /* plain text */
    }
    const message =
      typeof detail === "string"
        ? detail
        : (detail as { message?: string })?.message ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, message, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  users: () => request<User[]>("GET", "/users"),
  me: () => request<User>("GET", "/me"),
  stats: () => request<Stats>("GET", "/stats"),
  query: (question: string, mode: string, route = "auto") => request<QueryResponse>("POST", "/query", { question, mode, route }),
  feedback: (trace_id: string, rating: number) => request("POST", "/feedback", { trace_id, rating }),
  documents: () => request<DocumentRow[]>("GET", "/documents"),
  upload: (form: FormData) => request<{ version_id: string; doc_id: string; version_no: number; conflict: Conflict }>("POST", "/documents", undefined, form),
  tasks: () => request<Task[]>("GET", "/tasks"),
  decide: (taskId: string, decision: string, comment: string) =>
    request("POST", `/tasks/${taskId}/decision`, { decision, comment }),
  decideBatch: (batchId: string, decision: string, comment: string) =>
    request<{ decided: number }>("POST", `/tasks/batch/${batchId}/decision`, { decision, comment }),
  browse: (params: Record<string, string>) =>
    request<{ facets: Record<string, Facet[]>; documents: BrowseDoc[] }>("GET", `/browse?${new URLSearchParams(params)}`),
  audit: () => request<AuditRow[]>("GET", "/audit"),
};

/** PDFs are fetched with the X-User header and shown from a blob URL; #page jumps to the cited page. */
export async function openPdf(versionId: string, page?: number) {
  const win = window.open("", "_blank");
  const user = storedUser();
  const res = await fetch(`/api/documents/${versionId}/file`, { headers: user ? { "X-User": user } : {} });
  if (!res.ok) {
    win?.close();
    throw new ApiError(res.status, "Could not open document", null);
  }
  const url = URL.createObjectURL(await res.blob());
  if (win) win.location.href = page ? `${url}#page=${page}` : url;
}

export async function pdfBlobUrl(versionId: string): Promise<string> {
  const user = storedUser();
  const res = await fetch(`/api/documents/${versionId}/file`, { headers: user ? { "X-User": user } : {} });
  if (!res.ok) throw new ApiError(res.status, "Could not load document", null);
  return URL.createObjectURL(await res.blob());
}

/** Page images rendered by the API — fetched with X-User, returned as blob URLs. */
export async function pageImages(versionId: string): Promise<string[]> {
  const user = storedUser();
  const headers: Record<string, string> = user ? { "X-User": user } : {};
  const meta = await fetch(`/api/documents/${versionId}/pages`, { headers });
  if (!meta.ok) throw new ApiError(meta.status, "Could not load document", null);
  const { page_count } = (await meta.json()) as { page_count: number };
  return Promise.all(
    Array.from({ length: page_count }, async (_, i) => {
      const r = await fetch(`/api/documents/${versionId}/pages/${i + 1}`, { headers });
      return URL.createObjectURL(await r.blob());
    }),
  );
}
