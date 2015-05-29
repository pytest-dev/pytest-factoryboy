"""pytest-factoryboy pytest hooks."""


def pytest_factoryboy_done(request):
    """Called after all factory based fixtures and their post-generation actions were evaluated."""
