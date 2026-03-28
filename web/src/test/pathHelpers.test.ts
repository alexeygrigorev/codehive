import { describe, it, expect } from "vitest";
import {
  isAbsolutePath,
  pathBasename,
  pathJoin,
} from "@/pages/NewProjectPage";

describe("isAbsolutePath", () => {
  it("returns true for Unix absolute paths", () => {
    expect(isAbsolutePath("/home/user/myapp")).toBe(true);
    expect(isAbsolutePath("/")).toBe(true);
    expect(isAbsolutePath("/tmp")).toBe(true);
  });

  it("returns true for Windows drive letter paths", () => {
    expect(isAbsolutePath("C:\\Users\\alexey\\git\\myapp")).toBe(true);
    expect(isAbsolutePath("D:\\")).toBe(true);
    expect(isAbsolutePath("c:\\lowercase")).toBe(true);
    expect(isAbsolutePath("C:/forward/slashes")).toBe(true);
  });

  it("returns true for UNC paths (backslash)", () => {
    expect(isAbsolutePath("\\\\server\\share\\project")).toBe(true);
    expect(isAbsolutePath("\\\\server\\share")).toBe(true);
  });

  it("returns true for UNC paths (forward slash)", () => {
    expect(isAbsolutePath("//server/share/project")).toBe(true);
    expect(isAbsolutePath("//server/share")).toBe(true);
  });

  it("returns false for relative paths", () => {
    expect(isAbsolutePath("relative/path")).toBe(false);
    expect(isAbsolutePath("foo\\bar")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isAbsolutePath("")).toBe(false);
  });

  it("returns false for drive letter without separator (C:noslash)", () => {
    expect(isAbsolutePath("C:noslash")).toBe(false);
  });
});

describe("pathBasename", () => {
  it("returns basename for Unix paths", () => {
    expect(pathBasename("/home/user/myapp")).toBe("myapp");
    expect(pathBasename("/home/user/projects/myapp")).toBe("myapp");
  });

  it("returns basename for Windows paths", () => {
    expect(pathBasename("C:\\Users\\alexey\\git\\myapp")).toBe("myapp");
  });

  it("strips trailing separators before extracting basename", () => {
    expect(pathBasename("/home/user/myapp/")).toBe("myapp");
    expect(pathBasename("C:\\Users\\alexey\\git\\myapp\\")).toBe("myapp");
    expect(pathBasename("/home/user/myapp///")).toBe("myapp");
  });

  it("returns empty string for root paths", () => {
    expect(pathBasename("D:\\")).toBe("D:");
    // Unix root
    expect(pathBasename("/")).toBe("");
  });

  it("returns basename for UNC paths", () => {
    expect(pathBasename("\\\\server\\share\\project")).toBe("project");
    expect(pathBasename("//server/share/project")).toBe("project");
  });

  it("returns basename for relative paths", () => {
    expect(pathBasename("relative/path")).toBe("path");
  });

  it("returns empty string for empty input", () => {
    expect(pathBasename("")).toBe("");
  });
});

describe("pathJoin", () => {
  it("joins Unix paths with forward slash", () => {
    expect(pathJoin("/home/user/projects", "foo")).toBe(
      "/home/user/projects/foo",
    );
  });

  it("joins Unix paths and strips trailing slash", () => {
    expect(pathJoin("/home/user/projects/", "foo")).toBe(
      "/home/user/projects/foo",
    );
  });

  it("joins Windows paths with backslash", () => {
    expect(pathJoin("C:\\Users\\alexey\\projects", "foo")).toBe(
      "C:\\Users\\alexey\\projects\\foo",
    );
  });

  it("joins Windows paths and strips trailing backslash", () => {
    expect(pathJoin("C:\\Users\\alexey\\projects\\", "foo")).toBe(
      "C:\\Users\\alexey\\projects\\foo",
    );
  });

  it("returns just the name when base is empty", () => {
    expect(pathJoin("", "foo")).toBe("foo");
  });

  it("detects backslash separator even with mixed separators", () => {
    // If base contains any backslash, use backslash
    expect(pathJoin("C:\\Users/mixed", "foo")).toBe(
      "C:\\Users/mixed\\foo",
    );
  });
});
