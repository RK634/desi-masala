export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
export function authFetch(url: string, token: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...init, headers });
}
