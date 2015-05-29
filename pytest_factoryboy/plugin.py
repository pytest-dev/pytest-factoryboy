"""pytest-factoryboy plugin."""

import pytest


class Request(object):

    """PyTest FactoryBoy request."""

    def __init__(self):
        self.deferred = []
        self.is_finalized = False

    def defer(self, function):
        """Defer post-generation declaration execution until the end of the test setup.

        :param function: Function to be deferred.
        :note: Once already finalized all following defer calls will execute the function directly.
        """
        if self.is_finalized:
            function()
        else:
            self.deferred.append(function)

    def evaluate(self, names=None):
        """Finalize, run deferred post-generation actions, etc."""
        if names:
            functions = dict((function.__name__, function) for function in self.deferred if function.__name__ in names)
            deferred = [functions[name] for name in names if functions.get(name)]
        else:
            deferred = list(self.deferred)

        for function in deferred:
            function()
            self.deferred.remove(function)


@pytest.fixture
def factoryboy_request():
    """PyTest FactoryBoy request fixture."""
    return Request()


@pytest.mark.tryfirst
def pytest_runtest_call(item):
    """Before the test item is called."""
    try:
        request = item._request
    except AttributeError:
        # pytest-pep8 plugin passes Pep8Item here during tests.
        return
    factoryboy_request = request.getfuncargvalue("factoryboy_request")
    factoryboy_request.evaluate()
    factoryboy_request.is_finalized = True
    request.config.hook.pytest_factoryboy_done(request=request)


def pytest_addhooks(pluginmanager):
    """Register plugin hooks."""
    from pytest_factoryboy import hooks
    pluginmanager.addhooks(hooks)
