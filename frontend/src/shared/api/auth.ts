import type { ReactNode } from "react";

/** Estado mínimo de auth del shell (C-03 completa el cableado JWT). */
export interface AuthState {
  readonly token: string | null;
}

/** Storage key versionada (client-localstorage-schema: versionar y minimizar). */
const STORAGE_KEY = "turnos-odontologia/auth/v1";

export function readAuthState(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return { token: null };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === "object" && parsed !== null && "token" in parsed) {
      const token = (parsed as { token: unknown }).token;
      return { token: typeof token === "string" ? token : null };
    }
    return { token: null };
  } catch {
    return { token: null };
  }
}

export function writeAuthState(state: AuthState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: state.token }));
}

export function clearAuthState(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export type { ReactNode };
export { STORAGE_KEY };
