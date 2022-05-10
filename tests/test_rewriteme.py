import os
import pathlib
from unittest import mock


def test_rewrite_me(testdir):
    testfile = testdir.makepyfile((pathlib.Path(__file__).parent / "rewriteme.py").read_text())

    testrun = testdir.runpytest()
    assert testrun.ret != 0
    assert "You can let pytest-factoryboy rewrite your source code" in testrun.stdout.str()
    with mock.patch.dict(os.environ, os.environ | {"PYTEST_FACTORYBOY_REWRITE_SOURCE": "true"}):
        testrun = testdir.runpytest("-s")
        assert testrun.ret != 0
        assert f"Rewritten {testfile}" in testrun.stdout.str()

    rewritten_source = testfile.read_text("utf-8")

    testrun3 = testdir.runpytest_subprocess()
    assert testrun3.ret == 0

    testrun3.assert_outcomes(passed=6)


#     rewritten_source = testfile.read_text()
#     assert (
#         rewritten_source
#         == """\
# import factory
#
# from pytest_factoryboy import register
#
#
# class Author:
#     def __init__(self, name, last_name):
#         self.name = name
#         self.last_name = last_name
#
#
# @register
# @register(name="second_author_explicit_name_decorator")
# @register(factory_kwargs={"last_name": "Dickens as kwargs"})
# class AuthorFactory(factory.Factory):
#     class Meta:
#         model = Author
#
#     name = "Charles"
#     last_name = "Dickens"
#
#
# register(AuthorFactory, "third_author", factory_kwargs={"last_name": "Dickens as kwargs"})
# register(AuthorFactory, name="author_explicit_name_call")
# register(AuthorFactory, "partial_author", factory_kwargs{"name": "John Doe"})
# """
#     )
