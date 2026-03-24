# Testing & QA Best Practices

## Test Strategy
- Write tests alongside code, not as an afterthought.
- Aim for the testing pyramid: many unit tests, fewer integration tests, minimal E2E tests.
- Test behavior, not implementation details.
- Every bug fix should include a regression test.

## Python Testing (pytest)
- Use `pytest` as the test runner; configure in `pyproject.toml` or `pytest.ini`.
- Use fixtures for shared setup (`@pytest.fixture`).
- Use parametrize for testing multiple inputs: `@pytest.mark.parametrize`.
- Group tests by feature in `tests/` directory, mirroring `src/` structure.
- Name test files `test_*.py` and test functions `test_*`.

## Unit Tests
- Test one behavior per test function.
- Use descriptive names: `test_create_work_order_with_missing_field_returns_422`.
- Mock external dependencies (APIs, databases) in unit tests.
- Assert on specific values, not just truthiness.

## Integration Tests
- Test API endpoints with a test client (FastAPI's `TestClient`).
- Use a separate test database (SQLite in-memory or test-specific file).
- Test the full request/response cycle including validation and auth.
- Clean up test data between tests (use transactions or fresh DB).

## Test Organization
```
tests/
  conftest.py          # Shared fixtures
  test_api/
    test_customers.py
    test_work_orders.py
  test_models/
    test_customer.py
  test_services/
    test_scheduling.py
```

## Coverage
- Aim for 80%+ coverage on business logic; don't chase 100% everywhere.
- Use `pytest-cov` for coverage reporting.
- Exclude config, migrations, and test files from coverage metrics.

## Common Pitfalls
- Don't test framework behavior (e.g., that FastAPI returns 404 for missing routes).
- Don't write brittle tests that break on formatting changes.
- Don't use `time.sleep` in tests — use mocking or async test utilities.
- Don't ignore flaky tests — fix them or remove them.
