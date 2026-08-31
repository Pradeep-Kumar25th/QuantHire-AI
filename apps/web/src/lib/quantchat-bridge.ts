/** Open the dashboard QuantChat widget with a pre-filled prompt. */
export function openQuantChatWithPrompt(
  message: string,
  options?: { autoSend?: boolean },
) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("quanthire:quantchat-open", {
      detail: { message, expand: true, autoSend: options?.autoSend ?? false },
    }),
  );
}
