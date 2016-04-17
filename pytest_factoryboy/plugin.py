"""pytest-factoryboy plugin."""

from collections import defaultdict
import pytest


class Request(object):

    """PyTest FactoryBoy request."""

    def __init__(self, request):
        """Create pytest_factoryboy request.

        :param request: pytest request.
        """
        self.request = request
        self.deferred = []
        self.is_finalized = False
        self.results = defaultdict(dict)
        self.model_factories = {}

    def defer(self, function):
        """Defer post-generation declaration execution until the end of the test setup.

        :param function: Function to be deferred.
        :note: Once already finalized all following defer calls will execute the function directly.
        """
        self.deferred.append(function)
        if self.is_finalized:
            self.execute(function)

    def execute(self, function):
        """"Execute deferred function and store the result."""
        model, attr = function.__name__.split("__", 1)
        self.results[model][attr] = function(self.request)
        self.model_factories[model] = function._factory
        self.deferred.remove(function)

    def after_postgeneration(self):
        """Call _after_postgeneration hooks."""
        for model in list(self.results.keys()):
            results = self.results.pop(model)
            obj = self.request.getfuncargvalue(model)
            factory = self.model_factories[model]
            factory._after_postgeneration(obj=obj, create=True, results=results)

    def evaluate(self, names=None):
        """Finalize, run deferred post-generation actions, etc."""
        if names:
            functions = dict((function.__name__, function) for function in self.deferred if function.__name__ in names)
            deferred = [functions[name] for name in names if functions.get(name)]
        else:
            deferred = list(self.deferred)

        for function in deferred:
            self.execute(function)

        if not self.deferred:
            self.after_postgeneration()


@pytest.fixture
def factoryboy_request(request):
    """PyTest FactoryBoy request fixture."""
    return Request(request)


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
    # addhooks is for older py.test and deprecated; replaced by add_hookspecs
    add_hookspecs = getattr(pluginmanager, 'add_hookspecs', pluginmanager.addhooks)
    add_hookspecs(hooks)
