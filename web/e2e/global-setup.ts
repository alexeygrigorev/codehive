import fs from "fs";
import { TEST_DB_PATH } from "./e2e-constants";

/**
 * Playwright globalSetup: runs once before all tests.
 * Deletes the test database so every run starts with a clean slate.
 */
export default function globalSetup(): void {
  for (const suffix of ["", "-wal", "-shm"]) {
    const p = TEST_DB_PATH + suffix;
    if (fs.existsSync(p)) {
      fs.unlinkSync(p);
      console.log(`[global-setup] Deleted ${p}`);
    }
  }
}
