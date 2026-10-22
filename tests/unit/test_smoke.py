"""Smoke tests: the package and its subpackages import cleanly."""

import importlib

import pytest

SUBPACKAGES = ["config", "data", "retrieval", "evaluation", "generation", "api", "common"]


def test_package_imports() -> None:
    import rse

    assert isinstance(rse.__version__, str)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    importlib.import_module(f"rse.{name}")
