// examples/nodejs_example.js
// Node.js Fetch Integration Example for JARVIS REST API

const API_KEY = process.env.JARVIS_API_KEY || "default-jarvis-key";
const BASE_URL = "http://127.0.0.1:8000/api/v1";

async function main() {
  console.log("========================================");
  console.log("     JARVIS NODE.JS API CLIENT DEMO");
  console.log("========================================");

  // 1. Health Check
  const healthRes = await fetch(`${BASE_URL}/health`);
  console.log("[*] Health:", await healthRes.json());

  // 2. Execute Command
  const execRes = await fetch(`${BASE_URL}/execute`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-JARVIS-API-KEY": API_KEY,
    },
    body: JSON.stringify({ command: "Open Notepad" }),
  });
  console.log("[*] Execute Output:", await execRes.json());
}

main().catch(console.error);
