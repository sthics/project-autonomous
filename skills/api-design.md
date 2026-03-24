# API Design Best Practices

## RESTful Conventions
- Use nouns for resources: `/customers`, `/work-orders/{id}`.
- HTTP methods: GET (read), POST (create), PUT (full update), PATCH (partial update), DELETE.
- Return appropriate status codes: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity, 500 Internal Server Error.
- Use plural resource names consistently.

## Request/Response Format
- Always return JSON with consistent envelope: `{"data": ..., "error": null}`.
- Use camelCase for JSON keys in responses (even if backend uses snake_case).
- Include pagination for list endpoints: `?page=1&limit=20` with `total`, `page`, `limit` in response.
- Support filtering via query params: `?status=active&sort=-created_at`.

## Authentication & Authorization
- Use JWT tokens with short expiry (15-60 min) + refresh tokens.
- Store secrets in environment variables, never in code.
- Validate tokens on every request via middleware.
- Implement role-based access control (RBAC) for multi-tenant apps.

## Error Handling
- Return structured error responses: `{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [...]}}`.
- Never expose stack traces or internal details in production errors.
- Log full error details server-side at ERROR level.

## Security
- Configure CORS explicitly — never use `*` in production.
- Add rate limiting to all public endpoints (e.g., 100 req/min per IP).
- Validate and sanitize all input (query params, body, headers).
- Use HTTPS only; redirect HTTP to HTTPS.

## FastAPI-Specific
- Use Pydantic models for request/response validation.
- Use dependency injection for auth, database sessions.
- Add OpenAPI tags for endpoint grouping.
- Use `async def` for I/O-bound endpoints.

## Documentation
- Auto-generate OpenAPI/Swagger docs (FastAPI does this by default).
- Include example requests/responses for every endpoint.
- Document authentication requirements per endpoint.
