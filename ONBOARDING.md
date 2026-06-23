# Onboarding Guide

## Prerequisites

- Git, Docker, Node.js 20+, Python 3.11+
- Visual Studio Code (recommended)
- Windows: Visual Studio C++ Build Tools (for native modules)

## Setup Steps

1. Clone the repo
2. Run `scripts/onboard.ps1` (Windows) or `scripts/onboard.sh` (Linux/macOS)
3. Copy `.env.example` to `.env` and fill in secrets
4. Run `docker-compose up` to start the frontend SPA only
5. Access:

   - Frontend: <http://localhost:5173>

## Troubleshooting

- See `README.md` and `windows_service_setup.md` for platform-specific help
- For native module errors, ensure Visual Studio C++ Build Tools are installed

## References

- See `DEPLOYMENT.md`, `ARCHITECTURE.md`, `SECURITY_HEADERS.md` for more
