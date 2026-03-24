# DevOps & Deployment Best Practices

## Docker
- Use multi-stage builds to minimize image size.
- Pin base image versions (e.g., `python:3.12-slim`, not `python:latest`).
- Run as non-root user in production containers.
- Use `.dockerignore` to exclude `.git`, `node_modules`, `.venv`, etc.
- One process per container; use docker-compose for multi-service setups.

## Docker Compose (MVPs)
- Define all services in `docker-compose.yml`: app, db, reverse proxy.
- Use named volumes for persistent data (databases).
- Use environment variables for config; reference `.env` file.
- Expose only necessary ports; use internal networks for service-to-service.

## CI/CD
- Run linting, type checking, and tests on every push.
- Build and push Docker images on merge to main.
- Use GitHub Actions for CI; keep workflows under 10 minutes.
- Pin action versions (`uses: actions/checkout@v4`, not `@latest`).

## Deployment
- Use ports 8000-8999 for development; check availability before binding.
- Use a reverse proxy (nginx/Caddy) for SSL termination and static files.
- Set up health check endpoints (`/health`) for monitoring.
- Use environment-specific configs (dev, staging, prod).

## Security
- Never commit secrets — use env vars or secret managers.
- Keep dependencies updated; run `pip audit` / `npm audit` regularly.
- Enable security headers (HSTS, CSP, X-Frame-Options) via reverse proxy.
- Use read-only filesystem in containers where possible.

## Monitoring
- Structured JSON logging to stdout.
- Log at appropriate levels: DEBUG (dev only), INFO (normal ops), WARNING (degraded), ERROR (failures).
- Set up uptime monitoring for production endpoints.
- Track error rates and response times.

## Cleanup
- Remove unused Docker images/containers after task completion.
- Never use `sudo` for Docker — add user to docker group.
- Tag images with git SHA and `latest`.
