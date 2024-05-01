from __future__ import annotations

from dataclasses import *

import pytest
from factory import *

from pytest_factoryboy import register


@dataclass
class Company:
    name: str


@dataclass
class User:
    is_staff: bool
    company: Company | None


@register
class CompanyFactory(Factory):
    class Meta:
        model = Company

    name = "foo"


@register
class UserFactory(Factory):
    class Meta:
        model = User

    is_staff = False
    company = Maybe("is_staff", yes_declaration=None, no_declaration=SubFactory(CompanyFactory))


@pytest.mark.parametrize("user__is_staff", [False])
def test_staff_user_has_no_company_by_default(user):
    assert user.company is None


@pytest.mark.parametrize("user__is_staff", [False])
def test_normal_user_has_company_by_default(user, company):
    assert user.company is company
