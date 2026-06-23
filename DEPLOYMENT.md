# Deployment Guide

## Local Development

- Use `docker-compose up` to start the frontend SPA.
- Frontend: <http://localhost:5173>

## Production

- Set all secrets and environment variables in your deployment environment as needed.
- Use HTTPS and a reverse proxy such as Nginx or Caddy.
- Use `docker-compose -f docker-compose.yml up --build -d` for deployment.

## CI/CD

- See `.github/workflows/` for build, test, and deploy pipelines.

## Cloud/Container

- Compatible with most container platforms, including Azure, AWS, GCP, and DigitalOcean.
- For Kubernetes, adapt `docker-compose.yml` to manifests or use Kompose.

## References

- `ARCHITECTURE.md`
- `ONBOARDING.md`
- `SECURITY_HEADERS.md`
