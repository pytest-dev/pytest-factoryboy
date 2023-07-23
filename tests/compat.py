from __future__ import annotations

from importlib import metadata

from _pytest.pytester import RunResult
from packaging.version import Version

PYTEST_VERSION = Version(metadata.version("pytest"))

if PYTEST_VERSION >= Version("6.0.0"):

    def assert_outcomes(
        result: RunResult,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xpassed: int = 0,
        xfailed: int = 0,
    ) -> None:
        """Compatibility function for result.assert_outcomes"""
        result.assert_outcomes(
            errors=errors,
            passed=passed,
            skipped=skipped,
            failed=failed,
            xpassed=xpassed,
            xfailed=xfailed,
        )

else:

    def assert_outcomes(
        result: RunResult,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xpassed: int = 0,
        xfailed: int = 0,
    ) -> None:
        """Compatibility function for result.assert_outcomes"""
        result.assert_outcomes(
            error=errors,  # Pytest < 6 uses the singular form
            passed=passed,
            skipped=skipped,
            failed=failed,
            xpassed=xpassed,
            xfailed=xfailed,
        )  # type: ignore[call-arg]
