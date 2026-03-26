/**
 * JWT token utilities for decoding and validating tokens.
 */

export interface JWTPayload {
  sub: string; // user_id
  tenant_id: string;
  role: "member" | "admin" | "system_admin";
  exp: number; // expiration timestamp (seconds)
}

/**
 * Decode a JWT token and extract the payload.
 * Returns null if the token is invalid or cannot be decoded.
 */
export function decodeJWT(token: string): JWTPayload | null {
  try {
    // JWT structure: header.payload.signature
    const parts = token.split(".");
    if (parts.length !== 3) {
      return null;
    }

    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");

    // Decode base64 and parse JSON
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );

    return JSON.parse(jsonPayload) as JWTPayload;
  } catch (error) {
    console.error("Failed to decode JWT:", error);
    return null;
  }
}

/**
 * Check if a JWT token is expired.
 * Returns true if the token is expired or invalid.
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) {
    return true;
  }

  // exp is in seconds, Date.now() is in milliseconds
  return Date.now() >= payload.exp * 1000;
}

/**
 * Extract user information from a JWT token.
 * Returns null if the token is invalid or expired.
 */
export function getUserFromToken(token: string): {
  id: string;
  tenantId: string;
  role: "member" | "admin" | "system_admin";
} | null {
  if (isTokenExpired(token)) {
    return null;
  }

  const payload = decodeJWT(token);
  if (!payload) {
    return null;
  }

  return {
    id: payload.sub,
    tenantId: payload.tenant_id,
    role: payload.role,
  };
}
