import { apiCall } from "./client";

export function cleanupExpiredArtifacts() {
  return apiCall((client) => client.cleanupExpiredArtifacts());
}
