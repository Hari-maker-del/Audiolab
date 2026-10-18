const { neon } = require("@neondatabase/serverless");

module.exports = async function handler(request, response) {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  if (!process.env.DATABASE_URL) {
    return response.status(503).json({
      ok: false,
      service: "neon-postgres",
      error: "DATABASE_URL is not configured"
    });
  }

  try {
    const sql = neon(process.env.DATABASE_URL);
    const rows = await sql`select current_database() as database, now() as checked_at`;
    return response.status(200).json({
      ok: true,
      service: "neon-postgres",
      database: rows[0].database,
      checkedAt: rows[0].checked_at
    });
  } catch (error) {
    // Do not leak connection strings or database diagnostics to public clients.
    console.error("Audiolab Neon health check failed", error?.name || "DatabaseError");
    return response.status(503).json({
      ok: false,
      service: "neon-postgres",
      error: "Database connection failed"
    });
  }
};
