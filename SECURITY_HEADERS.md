# Security Headers

## Enforced Headers

- **Strict-Transport-Security**: max-age=63072000; includeSubDomains; preload
- **Content-Security-Policy**: default-src 'self'; base-uri 'self'; form-action 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; style-src-elem 'self'; style-src-attr 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'
- **X-Content-Type-Options**: nosniff
- **X-Frame-Options**: DENY
- **X-XSS-Protection**: 1; mode=block

## Implementation

- Set in FastAPI middleware (see `app/main.py`)
- Applied by the app middleware to current responses in every environment

## References

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Web Docs: Security Headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers)
