# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import pytest

from plum import (
    convert,
    add_conversion_method,
    add_promotion_rule,
    promote,
    conversion_method
)
from plum.promotion import _convert
from .test_signature import Num, Re, FP


class ConvertCache(object):
    """Revert methods of `convert` after you're done."""

    def __enter__(self):
        _convert._resolve_pending_registrations()
        self.methods = _convert.methods.copy()
        self.resolved = _convert._resolved.copy()

    def __exit__(self, exc_type, exc_val, exc_tb):
        _convert._resolve_pending_registrations()
        _convert.methods = self.methods
        _convert._resolved = self.resolved
        _convert.clear_cache()


def test_conversion():
    with ConvertCache():
        # Test basic conversion.
        assert convert(1.0, float) == 1.0
        assert convert(1.0, object) == 1.0
        with pytest.raises(TypeError):
            convert(1.0, int)

        # Test conversion with inheritance.
        r = Re()
        assert convert(r, Re) == r
        assert convert(r, Num) == r
        with pytest.raises(TypeError):
            convert(r, FP)

        # Test `add_conversion_method`.
        add_conversion_method(float, int, lambda _: 2.0)
        assert convert(1.0, float) == 1.0
        assert convert(1.0, object) == 1.0
        assert convert(1.0, int) == 2.0

        # Test `conversion_method`.
        @conversion_method(Num, FP)
        def num_to_fp(x):
            return 3.0

        assert convert(r, Re) == r
        assert convert(r, Num) == r
        assert convert(r, FP) == 3.0


def test_promotion():
    with ConvertCache():
        assert promote() == ()
        assert promote(1) == (1,)
        assert promote(1.) == (1.,)
        assert promote(1, 1) == (1, 1)
        assert promote(1., 1.) == (1., 1.)
        assert promote(1, 1, 1) == (1, 1, 1)
        assert promote(1., 1., 1.) == (1., 1., 1.)
        with pytest.raises(TypeError):
            promote(1, 1.)
        with pytest.raises(TypeError):
            promote(1., 1)

        add_promotion_rule(int, float, float)

        with pytest.raises(TypeError):
            promote(1, 1.)
        with pytest.raises(TypeError):
            promote(1., 1)

        add_conversion_method(int, float, float)

        assert promote(1, 1.) == (1., 1.)
        assert promote(1, 1, 1.) == (1., 1., 1.)
        assert promote(1., 1., 1) == (1., 1., 1.)

        with pytest.raises(TypeError):
            promote(1, '1')
        with pytest.raises(TypeError):
            promote('1', 1)
        with pytest.raises(TypeError):
            promote(1., '1')
        with pytest.raises(TypeError):
            promote('1', 1.)

        add_promotion_rule(str, {int, float}, {int, float})
        add_conversion_method(str, {int, float}, float)

        assert promote(1, '1', '1') == (1., 1., 1.)
        assert promote('1', 1, 1) == (1., 1., 1.)
        assert promote(1., '1', 1) == (1., 1., 1.)
        assert promote('1', 1., 1) == (1., 1., 1.)

        add_promotion_rule(str, int, float)
        add_promotion_rule(str, float, float)
        add_conversion_method(str, float, lambda x: 'lel')

        assert promote(1, '1', 1.) == (1., 'lel', 1.)
        assert promote('1', 1, 1.) == ('lel', 1., 1.)
        assert promote(1., '1', 1) == (1., 'lel', 1.)
        assert promote('1', 1., '1') == ('lel', 1., 'lel')


def test_inheritance():
    with ConvertCache():
        add_promotion_rule(Num, FP, Num)
        add_promotion_rule(Num, Re, Num)
        add_promotion_rule(FP, Re, Num)
        add_conversion_method(FP, Num, lambda x: 'Num from FP')
        add_conversion_method(Re, Num, lambda x: 'Num from Re')

        n = Num()
        assert promote(n, FP()) == (n, 'Num from FP')
        assert promote(Re(), n) == ('Num from Re', n)
        assert promote(Re(), FP()) == ('Num from Re', 'Num from FP')
