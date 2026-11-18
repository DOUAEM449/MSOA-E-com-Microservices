
const SESSION_KEY = "msoa-shop-session";

export async function apiRequest(baseUrl, path, options = {}) {
  let token = null;

  try {
    const session = JSON.parse(
      localStorage.getItem(SESSION_KEY)
    );
    token = session?.token ?? null;
  } catch {
    // No active session
  }

  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {}),
        ...options.headers
      }
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Cannot reach ${baseUrl}. Start the backend service and check its CORS settings.`,
        { cause: error }
      );
    }
    throw error;
  }

  if (response.status === 204) return null;

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const error = await response.json();
      message = error.message || message;
    } catch {
      // No JSON error body
    }

    const exception = new Error(message);
    exception.status = response.status;
    throw exception;
  }

  const body = await response.text();
  return body ? JSON.parse(body) : null;
}
