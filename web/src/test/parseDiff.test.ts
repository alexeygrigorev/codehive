import { describe, it, expect } from "vitest";
import { parseDiff } from "@/utils/parseDiff";

describe("parseDiff", () => {
  it("parses a single-file unified diff into structured data", () => {
    const diff = [
      "--- a/src/auth.py",
      "+++ b/src/auth.py",
      "@@ -1,3 +1,5 @@",
      " import os",
      "+import sys",
      "+import json",
      " ",
      "-old_line",
      " def main():",
    ].join("\n");

    const result = parseDiff(diff);
    expect(result).toHaveLength(1);
    expect(result[0].path).toBe("src/auth.py");
    expect(result[0].hunks).toHaveLength(1);

    const hunk = result[0].hunks[0];
    expect(hunk.oldStart).toBe(1);
    expect(hunk.oldCount).toBe(3);
    expect(hunk.newStart).toBe(1);
    expect(hunk.newCount).toBe(5);

    // Check line types
    const types = hunk.lines.map((l) => l.type);
    expect(types).toEqual([
      "context",
      "addition",
      "addition",
      "context",
      "deletion",
      "context",
    ]);

    // Check line numbers for an addition line
    const addLine = hunk.lines[1];
    expect(addLine.oldLineNumber).toBeNull();
    expect(addLine.newLineNumber).toBe(2);

    // Check line numbers for a deletion line
    const delLine = hunk.lines[4];
    expect(delLine.oldLineNumber).toBe(3);
    expect(delLine.newLineNumber).toBeNull();
  });

  it("parses a multi-file unified diff into multiple file entries", () => {
    const diff = [
      "--- a/a.py",
      "+++ b/a.py",
      "@@ -1 +1,2 @@",
      " line",
      "+added",
      "--- a/b.py",
      "+++ b/b.py",
      "@@ -1,2 +1 @@",
      " line",
      "-removed",
    ].join("\n");

    const result = parseDiff(diff);
    expect(result).toHaveLength(2);
    expect(result[0].path).toBe("a.py");
    expect(result[1].path).toBe("b.py");
  });

  it("returns an empty array for empty string", () => {
    expect(parseDiff("")).toEqual([]);
  });

  it("returns an empty array for blank/whitespace string", () => {
    expect(parseDiff("   \n  ")).toEqual([]);
  });

  it("correctly counts additions and deletions", () => {
    const diff = [
      "--- a/file.py",
      "+++ b/file.py",
      "@@ -1,4 +1,5 @@",
      " context",
      "+add1",
      "+add2",
      "+add3",
      "-del1",
      "-del2",
      " context",
    ].join("\n");

    const result = parseDiff(diff);
    expect(result[0].additions).toBe(3);
    expect(result[0].deletions).toBe(2);
  });
});
