import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dir = dirname(fileURLToPath(import.meta.url));

function runPython(script, args = []) {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", [join(__dir, script), ...args]);
    let out = "";
    let err = "";
    proc.stdout.on("data", (d) => (out += d));
    proc.stderr.on("data", (d) => (err += d));
    proc.on("close", (code) => {
      try {
        resolve(JSON.parse(out.trim()));
      } catch {
        reject(new Error(err.trim() || `python3 exited ${code}`));
      }
    });
  });
}

const server = new McpServer({
  name: "garmin-ble-mcp",
  version: "0.2.0",
});

server.tool(
  "get_realtime_heart_rate",
  "Get real-time heart rate directly from a BLE heart rate device (e.g. Garmin watch). Returns current BPM without needing Garmin Connect or internet.",
  { timeout_seconds: z.number().optional().describe("How long to scan for a device (default: 15s)") },
  async ({ timeout_seconds = 15 }) => {
    const result = await runPython("hr_reader.py", [String(timeout_seconds)]);
    if (result.error) throw new Error(result.error);
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

server.tool(
  "scan_ble_devices",
  "Scan for nearby Bluetooth LE devices that expose a heart rate service.",
  { timeout_seconds: z.number().optional().describe("Scan duration in seconds (default: 10)") },
  async ({ timeout_seconds = 10 }) => {
    const result = await runPython("scan_devices.py", [String(timeout_seconds)]);
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

server.tool(
  "get_hrv_analysis",
  "Collect RR intervals from the Garmin watch over a period and compute HRV metrics: RMSSD, SDNN, LF power, HF power, LF/HF ratio. LF/HF ratio indicates sympathetic/parasympathetic balance (high = stressed, low = relaxed). Requires heart rate broadcast mode on the watch. Default duration is 120 seconds; use at least 60s for meaningful results.",
  {
    duration_seconds: z.number().optional().describe(
      "How long to collect data in seconds (default: 120, minimum recommended: 60)"
    ),
  },
  async ({ duration_seconds = 120 }) => {
    const result = await runPython("hrv_reader.py", [String(duration_seconds)]);
    if (result.error) throw new Error(result.error);
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(console.error);
