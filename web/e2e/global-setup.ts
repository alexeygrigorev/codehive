import fs from "fs";
import { TEST_DB_PATH, E2E_TEMP_DIR } from "./e2e-constants";

/**
 * Playwright globalSetup: runs once before all tests.
 * - Deletes the test database so every run starts with a clean slate.
 * - Recreates the e2e temp directory so tests have a valid base dir.
 */
export default function globalSetup(): void {
  for (const suffix of ["", "-wal", "-shm"]) {
    const p = TEST_DB_PATH + suffix;
    if (fs.existsSync(p)) {
      fs.unlinkSync(p);
      console.log(`[global-setup] Deleted ${p}`);
    }
  }

  // Remove and recreate the e2e temp directory for a clean slate
  if (fs.existsSync(E2E_TEMP_DIR)) {
    fs.rmSync(E2E_TEMP_DIR, { recursive: true, force: true });
    console.log(`[global-setup] Removed ${E2E_TEMP_DIR}`);
  }
  fs.mkdirSync(E2E_TEMP_DIR, { recursive: true });
  console.log(`[global-setup] Created ${E2E_TEMP_DIR}`);
}
