import { defineConfig } from "@neondatabase/config/v1";

/**
 * Audiolab's requested Neon service scope is Postgres only.
 * Authentication and object storage are deliberately not enabled here.
 * No paid AI gateway or GPU is provisioned.
 */
export default defineConfig({});
