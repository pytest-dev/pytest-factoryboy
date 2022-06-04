from tests.compat import assert_outcomes


def test_non_standard_subfactory_name(testdir):
    """Test that an error is raised if the fixture name can't be determined."""
    testdir.makepyfile(
        """
        from __future__ import annotations
        from dataclasses import dataclass

        import factory

        from pytest_factoryboy import register

        class Owner:
            pass


        class Foo:
            def __init__(self, owner: Owner):
                self.owner = owner


        @register(_name="owner")
        class OwnerMaker(factory.Factory):
            class Meta:
                model = Owner


        @register()
        class FooFactory(factory.Factory):
            class Meta:
                model = Foo

            owner = factory.SubFactory(OwnerMaker)


        def test_foo_maker(foo):
            assert foo.owner
    """
    )
    res = testdir.runpytest()
    assert_outcomes(res, errors=1)

    res.stdout.fnmatch_lines("*not able to detect*subfactory <OwnerMaker *for *Owner*")
