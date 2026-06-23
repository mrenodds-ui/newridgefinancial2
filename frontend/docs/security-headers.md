# Security Headers for Production

Add these headers in your hosting/CDN config (Vercel, Netlify, Cloudflare Pages, or nginx):

## Content-Security-Policy (CSP)
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self';
```
- Adjust `connect-src` for your API endpoints.
- For stricter CSP, avoid `'unsafe-inline'` and use hashed styles.

## Permissions-Policy
```
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=(), vr=(), accelerometer=(), gyroscope=(), magnetometer=(), fullscreen=(), sync-xhr=()
```
- Disable all unused browser features.

## Referrer-Policy
```
Referrer-Policy: strict-origin-when-cross-origin
```

## X-Content-Type-Options
```
X-Content-Type-Options: nosniff
```

## Example (Netlify _headers file)
```
/*
  Content-Security-Policy: ...
  Permissions-Policy: ...
  Referrer-Policy: strict-origin-when-cross-origin
  X-Content-Type-Options: nosniff
```

## Notes
- Test your headers with [securityheaders.com](https://securityheaders.com/).
- If you use a service worker, ensure CSP allows `service-worker` registration.
- Never allow `unsafe-eval` or wildcards in production CSP.
