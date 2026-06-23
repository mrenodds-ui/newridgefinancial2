import { describe, expect, it } from "vitest";

import { sanitizeHtml } from "../security/sanitizeHtml";

describe("sanitizeHtml", () => {
  it("removes script tags and event handlers", () => {
    const unsafe = '<div onclick="alert(1)">safe</div><script>alert("x")</script>';
    const sanitized = sanitizeHtml(unsafe);

    expect(sanitized).toContain("<div>safe</div>");
    expect(sanitized).not.toContain("onclick");
    expect(sanitized).not.toContain("<script");
  });

  it("removes javascript: urls and SVG script vectors", () => {
    const unsafe = '<a href="javascript:alert(1)">x</a><svg><g onload="alert(1)"></g></svg>';
    const sanitized = sanitizeHtml(unsafe);

    expect(sanitized).not.toContain("javascript:");
    expect(sanitized).not.toContain("onload");
  });
});
