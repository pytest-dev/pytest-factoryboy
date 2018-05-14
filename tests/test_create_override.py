import factory

from pytest_factoryboy import register

from .django_app.model import Bar


class BaseBarFactory(factory.DjangoModelFactory):
    """Base Bar factory."""

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        bar = super(BaseBarFactory, cls)._create(model_class, *args, **kwargs)
        bar.wrong = 'spam'
        return bar

    class Meta:
        model = Bar


class BarFactory(BaseBarFactory):
    """Bar factory."""

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        bar = super(BaseBarFactory, cls)._create(model_class, *args, **kwargs)
        bar.right = 'foo'
        return bar

    class Meta:
        model = Bar


register(BarFactory, 'bar')


def test_create_is_called(db, bar, bar_factory):
    # FactoryBoy fixture works fine
    bar_no_register = BarFactory()
    assert getattr(bar_no_register, 'wrong') is None
    assert getattr(bar_no_register, 'right') == 'foo'

    # registered factory works fine
    registered_bar = bar_factory()
    assert getattr(registered_bar, 'wrong') is None
    assert getattr(registered_bar, 'right') == 'foo'

    # registered instance works fine
    assert getattr(bar, 'wrong') is None
    assert getattr(bar, 'right') == 'foo'
