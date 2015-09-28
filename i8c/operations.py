from i8c.parser import synthetic_node
from i8c import visitors

class Operation(visitors.Visitable):
    """Base class for all operations.
    """
    def __init__(self, ast):
        self.ast = ast

    @property
    def fileline(self):
        return self.ast.fileline

    @property
    def source(self):
        """Source file text this operation was created from.
        """
        return " ".join((token.text for token in self.ast.tokens))

    @property
    def is_block_terminal(self):
        return isinstance(self, TerminalOp)

    @property
    def is_branch(self):
        return isinstance(self, BranchOp)

    @property
    def is_goto(self):
        return isinstance(self, GotoOp)

    @property
    def is_return(self):
        return isinstance(self, ReturnOp)

    @property
    def is_comparison(self):
        return isinstance(self, CompareOp)

    @property
    def is_load_constant(self):
        return isinstance(self, ConstOp)

    @property
    def is_add(self):
        return isinstance(self, AddOp)

    def __eq__(self, other):
        return not (self != other)

    def __ne__(self, other):
        raise NotImplementedError, "%s.__ne__" % self.classname

    def __str__(self):
        return '%s("%s")' % (self.classname, self.source)

# XXX

class NameFromSourceMixin:
    @property
    def dwarfname(self):
        return self.ast.tokens[0].text

# Operations that can be compared just by comparing their class.
# We check two ways to allow regular and synthetic operations to
# be equal.

class ClassComparableOp(Operation):
    def __eq__(self, other):
        return (isinstance(self, other.__class__)
                or isinstance(other, self.__class__))

    def __ne__(self, other):
        return not (self == other)

# Block-terminating operations.  Note that these are class-comparable,
# meaning exits are not checked, only the operations themselves.  Code
# comparing block-terminating operations must ensure exits are also
# checked if required.

class TerminalOp(ClassComparableOp):
    """Base class for operations that terminate their basic block.
    """

class BranchOp(TerminalOp):
    BRANCHED_EXIT = 0
    NOBRANCH_EXIT = 1

    dwarfname = "bra"

    @property
    def exit_labels(self):
        yield self.ast.target.name
        yield self.fallthrough

class GotoOp(TerminalOp):
    dwarfname = "skip"

    @property
    def exit_labels(self):
        yield self.ast.target.name

class ReturnOp(TerminalOp):
    exit_labels = ()

# Synthetic block-terminating operations

class SyntheticGoto(GotoOp):
    def __init__(self, template, target=None):
        GotoOp.__init__(self, synthetic_node(template.ast, "goto"))
        if target is not None:
            self.target = target

    @property
    def exit_labels(self):
        yield self.target

class SyntheticReturn(ReturnOp):
    def __init__(self, template):
        ReturnOp.__init__(self, synthetic_node(template.ast, "return"))

# XXX

class SimpleUnaryOp(ClassComparableOp, NameFromSourceMixin):
    """An operator with no operands that pops one value and pushes one
    back."""

class SimpleBinaryOp(ClassComparableOp, NameFromSourceMixin):
    """An operator with no operands that pops two values and pushes
    one back."""

# XXX

AbsOp = SimpleUnaryOp
AndOp = SimpleBinaryOp

class AddOp(SimpleBinaryOp):
    dwarfname = "plus"

class PlusUConst(Operation):
    dwarfname = "plus_uconst"

    def __init__(self, template):
        assert template.value != 0
        Operation.__init__(self, template.ast)
        self.value = template.value

class CallOp(ClassComparableOp):
    dwarfname = "GNU_i8call"

class CompareOp(Operation):
    REVERSE = {"lt": "ge", "le": "gt", "eq": "ne",
               "ne": "eq", "ge": "lt", "gt": "le"}

    def __init__(self, ast):
        Operation.__init__(self, ast)
        self.reversed = False

    @property
    def dwarfname(self):
        name = self.ast.tokens[0].text[-2:]
        if self.reversed:
            name = self.REVERSE[name]
        return name

    def reverse(self):
        self.reversed = not self.reversed

class ConstOp(Operation):
    @property
    def type(self):
        return self.ast.operand.type

    @property
    def value(self):
        return self.ast.operand.value

class DerefOp(Operation):
    @property
    def type(self):
        return self.ast.operand.type

DivOp = SimpleBinaryOp

class DropOp(ClassComparableOp, NameFromSourceMixin):
    pass

class DupOp(ClassComparableOp, NameFromSourceMixin):
    pass

ModOp = SimpleBinaryOp
MulOp = SimpleBinaryOp

class NameOp(Operation):
    @property
    def name(self):
        return self.ast.name.value

    @property
    def slot(self):
        return self.ast.slot.value

NegOp = SimpleUnaryOp
NotOp = SimpleUnaryOp
OrOp = SimpleBinaryOp

class OverOp(ClassComparableOp, NameFromSourceMixin):
    pass

class PickOp(Operation):
    @property
    def operand(self):
        return self.ast.operand

ShlOp = SimpleBinaryOp
ShrOp = SimpleBinaryOp # Welcome to Shropshire
ShraOp = SimpleBinaryOp

class SubOp(SimpleBinaryOp):
    dwarfname = "minus"

class SwapOp(ClassComparableOp, NameFromSourceMixin):
    pass

class RotOp(ClassComparableOp, NameFromSourceMixin):
    pass

XorOp = SimpleBinaryOp
