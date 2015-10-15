# -*- coding: utf-8 -*-
# Copyright (C) 2015 Red Hat, Inc.
# This file is part of the Infinity Note Compiler.
#
# The Infinity Note Compiler is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# The Infinity Note Compiler is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with the Infinity Note Compiler.  If not, see
# <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from i8c.tests import TestCase

# In this miscompilation the final "call" was dropped as unreachable
SOURCE = """\
define test::bug_0001 returns int, ptr
    argument int arg1
    extern func int, ptr (int) func1
    extern func int () func2
    extern ptr sym1

    deref ptr
    load NULL
    bne label2
    swap
    drop
    load NULL
    rot
    call
    beq label1
    load 1
    return
label1:
    load 0
    return
label2:
    drop
    call
"""

class TestBug0001(TestCase):
    def test_bug_0001(self):
        """Miscompilation check #0001"""
        tree, output = self.compile(SOURCE)
        ops = output.opnames
        # Robust test: check the stream contains two DW_OP_GNU_i8calls.
        # They refer to different functions so there's no way the two
        # can be combined.
        self.assertEqual(len([op for op in ops if op == "GNU_i8call"]), 2)
        # Fragile test: check that the stream is as we expect.
        # This may need fixing up to cope with future compiler changes.
        self.assertEqual(["deref", "bra", "swap", "drop",
                          "lit0", "rot", "GNU_i8call", "ne",
                          "skip", "drop", "GNU_i8call"], ops)
