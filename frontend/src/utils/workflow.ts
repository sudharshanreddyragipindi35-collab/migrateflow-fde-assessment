export function friendlyWorkflowMessage(message: string) {
  const normalized = message.toLowerCase();
  if (normalized.includes("batch response") || normalized.includes("source column")) {
    return "The model returned an incomplete response. No data was changed. Select Retry safely; MigrateFlow will retry once, then route clearly labelled fallback proposals to human review.";
  }
  if (normalized.includes("unavailable") || normalized.includes("connection")) {
    return "The model is temporarily unavailable. No data was changed. Check Ollama and select Retry safely.";
  }
  return message;
}
