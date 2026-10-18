import { neon } from "@neondatabase/serverless";

if (!process.env.DATABASE_URL) {
  console.error("Neon smoke test blocked: DATABASE_URL is missing. Run Neon CLI setup first.");
  process.exit(2);
}

try {
  const sql = neon(process.env.DATABASE_URL);
  const rows = await sql`select 1::int as value, current_database() as database`;
  if (rows[0]?.value !== 1 || !rows[0]?.database) {
    throw new Error("Unexpected result from Neon database.");
  }
  console.log(`Neon smoke test passed: connected to database "${rows[0].database}" and SELECT 1 returned 1.`);
} catch (error) {
  console.error(`Neon smoke test failed: ${error?.message || "unknown database error"}`);
  process.exit(1);
}
