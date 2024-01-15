import pytest

import fbx_plum
from fbx_plum.promotion import _convert, _promotion_rule


@pytest.fixture
def convert():
    # Save methods.
    _convert._resolve_pending_registrations()
    resolved = list(_convert._resolved)

    yield fbx_plum.convert

    # Clear methods after use.
    _convert._resolve_pending_registrations()
    _convert._pending = []
    _convert._resolved = resolved
    _convert.clear_cache(reregister=True)


@pytest.fixture
def promote():
    # Save methods.
    _promotion_rule._resolve_pending_registrations()
    resolved = list(_promotion_rule._resolved)

    yield fbx_plum.promote

    # Clear methods after use.
    _promotion_rule._pending = []
    _promotion_rule._resolved = resolved
    _promotion_rule.clear_cache(reregister=True)
