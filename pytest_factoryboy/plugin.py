"""pytest-factoryboy plugin."""

import pytest


class Request(object):

    """PyTest FactoryBoy request."""

    def __init__(self):
        self.deferred = []
        self.is_evaluated = False

    def defer(self, function):
        """Defer post-generation declaration execution until the end of the test setup.

        :param function: Function to be deferred.
        :note: Once already evaluated all following defer calls will execute the function directly.
        """
        if self.is_evaluated:
            function()
        else:
            self.deferred.append(function)

    def evaluate(self):
        """Finalize, run deferred post-generation actions, etc."""
        while True:
            try:
                self.deferred.pop(0)()
            except IndexError:
                return
            finally:
                self.is_evaluated = True


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
    request.getfuncargvalue("factoryboy_request").evaluate()
    request.config.hook.pytest_factoryboy_done(request=request)


def pytest_addhooks(pluginmanager):
    """Register plugin hooks."""
    from pytest_factoryboy import hooks
    pluginmanager.addhooks(hooks)
