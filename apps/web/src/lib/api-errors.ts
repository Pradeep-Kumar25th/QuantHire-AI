import axios from "axios";

/** Extract a readable error string from axios or fetch failures. */
export function getApiErrorMessage(
  error: unknown,
  fallback = "Request failed",
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
    const response = data?.response;
    if (typeof response === "string" && response.trim()) {
      return response;
    }
    const nestedError = data?.error as Record<string, unknown> | undefined;
    const nestedMessage = nestedError?.message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) {
      return nestedMessage;
    }
    const message = data?.message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    if (error.response?.status) {
      return `Request failed (HTTP ${error.response.status})`;
    }
    if (error.message === "Network Error" && error.response) {
      return `Request failed (HTTP ${error.response.status})`;
    }
    if (error.message) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
