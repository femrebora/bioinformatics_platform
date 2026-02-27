import axios from "axios";
import type { AuthUser, TokenResponse } from "../types/auth";

const http = axios.create({ baseURL: "/api/v1" });

export const TOKEN_KEY = "bio_platform_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function register(email: string, password: string): Promise<AuthUser> {
  const { data } = await http.post<AuthUser>("/auth/register", { email, password });
  return data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  // OAuth2PasswordRequestForm requires application/x-www-form-urlencoded
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  const { data } = await http.post<TokenResponse>("/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function getMe(token: string): Promise<AuthUser> {
  const { data } = await http.get<AuthUser>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}
