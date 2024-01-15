import typing
from typing import List, Union

import pytest

import fbx_plum
from fbx_plum import ModuleType


@pytest.mark.xfail()
def test_beartype_on_strategy():
    # The `O(n)` strategy is not yet supported.
    for _ in range(10):
        assert not fbx_plum.isinstance([1, 1, 1, 1, None], List[int])


def test_isinstance():
    # Check that subscripted generics work and types are resolved.
    assert fbx_plum.isinstance(
        1,
        Union[float, ModuleType("builtins", "int")],  # noqa: F821
    )


def test_issubclass():
    # Check that subscripted generics work and types are resolved.
    assert fbx_plum.issubclass(
        Union[ModuleType("builtins", "int"), float],  # noqa: F821
        Union[ModuleType("numbers", "Number"), complex],  # noqa: F821
    )


def test_backward_compatibility():
    assert fbx_plum.Dict == typing.Dict
    assert fbx_plum.List == typing.List
    assert fbx_plum.Tuple == typing.Tuple
    assert fbx_plum.Union == typing.Union
