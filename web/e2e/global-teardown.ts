import fs from "fs";
import { E2E_TEMP_DIR } from "./e2e-constants";

/**
 * Playwright globalTeardown: runs once after all tests.
 * Removes the e2e temp directory so no test artifacts are left behind.
 */
export default function globalTeardown(): void {
  if (fs.existsSync(E2E_TEMP_DIR)) {
    fs.rmSync(E2E_TEMP_DIR, { recursive: true, force: true });
    console.log(`[global-teardown] Removed ${E2E_TEMP_DIR}`);
  }
}
