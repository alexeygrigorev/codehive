/** Structured representation of a parsed unified diff. */

export interface DiffLine {
  type: "addition" | "deletion" | "context";
  content: string;
  oldLineNumber: number | null;
  newLineNumber: number | null;
}

export interface DiffHunk {
  oldStart: number;
  oldCount: number;
  newStart: number;
  newCount: number;
  lines: DiffLine[];
}

export interface DiffFile {
  path: string;
  hunks: DiffHunk[];
  additions: number;
  deletions: number;
}

/**
 * Parse a unified diff string into structured data.
 *
 * Handles multi-file diffs separated by `--- a/...` / `+++ b/...` headers.
 * Returns an empty array for empty or blank input.
 */
export function parseDiff(diffText: string): DiffFile[] {
  if (!diffText || !diffText.trim()) {
    return [];
  }

  const files: DiffFile[] = [];
  const lines = diffText.split("\n");
  let i = 0;

  while (i < lines.length) {
    // Look for a file header pair: --- a/... then +++ b/...
    if (lines[i].startsWith("--- ") && i + 1 < lines.length && lines[i + 1].startsWith("+++ ")) {
      const plusLine = lines[i + 1];
      // Extract path from +++ b/path or +++ path
      let path = plusLine.slice(4);
      if (path.startsWith("b/")) {
        path = path.slice(2);
      }

      i += 2; // skip past --- and +++

      const hunks: DiffHunk[] = [];
      let additions = 0;
      let deletions = 0;

      // Parse hunks until next file header or end
      while (i < lines.length && !lines[i].startsWith("--- ")) {
        if (lines[i].startsWith("@@ ")) {
          const hunk = parseHunkHeader(lines[i]);
          i++;

          // Parse lines within this hunk
          let oldLine = hunk.oldStart;
          let newLine = hunk.newStart;

          while (i < lines.length && !lines[i].startsWith("@@ ") && !lines[i].startsWith("--- ")) {
            const line = lines[i];
            if (line.startsWith("+")) {
              hunk.lines.push({
                type: "addition",
                content: line.slice(1),
                oldLineNumber: null,
                newLineNumber: newLine,
              });
              newLine++;
              additions++;
            } else if (line.startsWith("-")) {
              hunk.lines.push({
                type: "deletion",
                content: line.slice(1),
                oldLineNumber: oldLine,
                newLineNumber: null,
              });
              oldLine++;
              deletions++;
            } else if (line.startsWith(" ") || line === "") {
              // Context line (or empty trailing line)
              const content = line.startsWith(" ") ? line.slice(1) : line;
              // Skip truly empty trailing lines at end of diff
              if (line === "" && i === lines.length - 1) {
                i++;
                break;
              }
              hunk.lines.push({
                type: "context",
                content,
                oldLineNumber: oldLine,
                newLineNumber: newLine,
              });
              oldLine++;
              newLine++;
            } else {
              // Unknown line format (e.g. "\ No newline at end of file"), skip
              i++;
              continue;
            }
            i++;
          }

          hunks.push(hunk);
        } else {
          i++;
        }
      }

      files.push({ path, hunks, additions, deletions });
    } else {
      i++;
    }
  }

  return files;
}

function parseHunkHeader(line: string): DiffHunk {
  // @@ -oldStart,oldCount +newStart,newCount @@
  const match = line.match(/@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
  if (!match) {
    return { oldStart: 1, oldCount: 0, newStart: 1, newCount: 0, lines: [] };
  }
  return {
    oldStart: parseInt(match[1], 10),
    oldCount: match[2] !== undefined ? parseInt(match[2], 10) : 1,
    newStart: parseInt(match[3], 10),
    newCount: match[4] !== undefined ? parseInt(match[4], 10) : 1,
    lines: [],
  };
}
