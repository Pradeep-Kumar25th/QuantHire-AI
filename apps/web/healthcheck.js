// Minimal container health check for Next.js production server.
const http = require("http");

http
  .get("http://127.0.0.1:3000/", (res) => {
    process.exit(res.statusCode && res.statusCode < 500 ? 0 : 1);
  })
  .on("error", () => process.exit(1));
