import DOMPurify from "dompurify";

type TrustedTypePolicy = {
  createHTML: (input: string) => string;
};

const SANITIZER_OPTIONS = {
  USE_PROFILES: { html: true },
  RETURN_TRUSTED_TYPE: false,
} as const;

// Trusted Types policy (feature-detected, paired with DOMPurify)
// Use cross-browser safe feature detection and type declaration
declare global {
  interface Window {
    trustedTypes?: {
      createPolicy: (name: string, rules: { createHTML: (input: string) => string }) => TrustedTypePolicy;
    };
  }
}
let trustedTypesPolicy: TrustedTypePolicy | undefined;

function getTrustedTypesPolicy(): TrustedTypePolicy | undefined {
  if (trustedTypesPolicy !== undefined) {
    return trustedTypesPolicy;
  }

  if (typeof window === "undefined" || !window.trustedTypes?.createPolicy) {
    trustedTypesPolicy = undefined;
    return undefined;
  }

  try {
    trustedTypesPolicy = window.trustedTypes.createPolicy("default", {
      createHTML: (input: string) => DOMPurify.sanitize(input, SANITIZER_OPTIONS),
    });
  } catch {
    trustedTypesPolicy = undefined;
  }

  return trustedTypesPolicy;
}

export function sanitizeHtml(input: string): string {
  if (!input) {
    return "";
  }
  const policy = getTrustedTypesPolicy();
  if (policy) {
    return policy.createHTML(input);
  }
  return DOMPurify.sanitize(input, SANITIZER_OPTIONS);
}
