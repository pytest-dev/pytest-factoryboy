import factory

from pytest_factoryboy import register


class Author:
    def __init__(self, name, last_name):
        self.name = name
        self.last_name = last_name


@register
@register(_name="second_author_explicit_name_decorator")
@register(last_name="Dickens as kwargs")
class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles"
    last_name = "Dickens"


register(AuthorFactory, "third_author", last_name="Dickens as kwargs")
register(AuthorFactory, _name="author_explicit_name_call")
register(AuthorFactory, "partial_author", name="John Doe")
register(AuthorFactory, "author", model_name="attr of the factory")
