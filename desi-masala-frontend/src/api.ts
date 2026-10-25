export type SupportedLanguage = "en" | "de" | "fr" | "es" | "pl" | "hi";

export const SUPPORTED_LANGUAGES: SupportedLanguage[] = [
  "en",
  "de",
  "fr",
  "es",
  "pl",
  "hi",
];

export interface ApiProduct {
  id: number;
  name: string;
  price: number;
  brand: string | null;
  stock_quantity: number;
  description?: string | null;
  category?: string | null;
  image_url?: string | null;
  discount_percent?: number;
  is_featured?: boolean;
  is_new_arrival?: boolean;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: "customer" | "admin";
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
}

export interface RegisterPayload {
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address_line1: string;
  postal_code: string;
  city: string;
  country: string;
  marketing_opt_in: boolean;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  account_type: "customer" | "admin";
  remember_me: boolean;
}

export const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function normalizeLanguage(language: string): SupportedLanguage {
  const normalized = language.toLowerCase().split("-")[0];

  if (
    SUPPORTED_LANGUAGES.includes(normalized as SupportedLanguage)
  ) {
    return normalized as SupportedLanguage;
  }

  return "en";
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string;
      message?: string;
    };

    return (
      body.detail ||
      body.message ||
      `Request failed (${response.status}).`
    );
  } catch {
    return `Request failed (${response.status}).`;
  }
}

async function postJson<T>(
  path: string,
  payload: unknown,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json() as Promise<T>;
}

/**
 * Fetch products in the selected language.
 *
 * The backend must support:
 * GET /products?language=en
 * GET /products?language=de
 * GET /products?language=fr
 * GET /products?language=es
 * GET /products?language=pl
 * GET /products?language=hi
 */
export async function fetchProducts(
  language: string = "en",
): Promise<ApiProduct[]> {
  const selectedLanguage = normalizeLanguage(language);

  const response = await fetch(
    `${API_URL}/products?language=${encodeURIComponent(selectedLanguage)}`,
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json() as Promise<ApiProduct[]>;
}

export async function registerCustomer(
  payload: RegisterPayload,
): Promise<{ message: string }> {
  return postJson<{ message: string }>(
    "/auth/register",
    payload,
  );
}

export async function loginCustomer(
  payload: LoginPayload,
): Promise<AuthResponse> {
  return postJson<AuthResponse>(
    "/auth/login",
    payload,
  );
}

export async function verifyEmailCode(
  email: string,
  code: string,
): Promise<{ message: string }> {
  return postJson<{ message: string }>(
    "/auth/verify-code",
    { email, code },
  );
}

export async function resendVerification(
  email: string,
): Promise<{ message: string }> {
  return postJson<{ message: string }>(
    "/auth/resend-verification",
    { email },
  );
}
