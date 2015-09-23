from i8c.exceptions import ParserError, ParsedError
from i8c import lexer
from i8c.lexer import synthetic_token
from i8c import logger
from i8c import visitors
import copy

debug_print = logger.debug_printer_for(__name__)

class TreeNode(visitors.Visitable):
    def __init__(self):
        self.tokens = []
        self.children = []

    @property
    def fileline(self):
        return self.tokens[0].fileline

    def add_child(self, klass):
        child = klass()
        self.children.append(child)
        return child

    @property
    def latest_child(self):
        return self.children[-1]

    def some_children(self, classinfo):
        return (child
                for child in self.children
                if isinstance(child, classinfo))

    def one_child(self, classinfo):
        result = None
        for child in self.some_children(classinfo):
            if result is not None:
                self.__one_child_error("multiple", classinfo)
            result = child
        if result is None:
            self.__one_child_error("no", classinfo)
        return result

    def __one_child_error(self, what, classinfo):
        msg = "%s has %s %s" % (
            self.classname,
            what,
            classinfo.__name__)
        raise ParsedError(self, msg.lower())

    def __str__(self):
        lines = []
        self.__dump(lines, "")
        return "\n".join(lines)

    def __dump(self, lines, prefix):
        line = prefix + self.classname
        if isinstance(self, LeafNode):
            line += ': '
            line += " ".join((token.text for token in self.tokens))
        if hasattr(self, "type"):
            # Dump what the type annotator added
            line += " [%s]" % self.type.name
        lines.append(line)
        for child in self.children:
            child.__dump(lines, prefix + "  ")

class LeafNode(TreeNode):
    def consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = tokens

class SyntheticNode(LeafNode):
    """A node that the block creator created.
    """
    def __init__(self, template, text):
        self.tokens = [synthetic_token(template.tokens[0],
                                       "synthetic " + text)]

synthetic_node = SyntheticNode

class Identifier(LeafNode):
    def consume(self, tokens):
        if len(tokens) != 1 or not isinstance(tokens[0], lexer.WORD):
            raise ParserError(tokens)
        LeafNode.consume(self, tokens)

    @property
    def name(self):
        return self.tokens[0].text

class Constant(LeafNode):
    def consume(self, tokens):
        if len(tokens) != 1:
            raise ParserError(tokens)
        LeafNode.consume(self, tokens)

class Integer(Constant):
    def consume(self, tokens):
        Constant.consume(self, tokens)
        if not isinstance(self.tokens[0], lexer.NUMBER):
            raise ParserError(tokens)
        self.value = self.tokens[0].value

class BuiltinConstant(Constant):
    def consume(self, tokens):
        Constant.consume(self, tokens)
        self.value = self.VALUES.get(tokens[0].text, None)
        if self.value is None:
            raise ParserError(tokens)

class Pointer(BuiltinConstant):
    VALUES = {"NULL": 0}

class Boolean(BuiltinConstant):
    VALUES = {"TRUE": 1, "FALSE": 0}

class TopLevel(TreeNode):
    def consume(self, tokens):
        if tokens[0].text == "define":
            if len(tokens) < 2:
                raise ParserError(tokens)
            if tokens[1].text == "type":
                self.add_child(TypeDef)
            else:
                self.add_child(Function)
        elif not self.children:
            raise ParserError(tokens)
        self.latest_child.consume(tokens)

    @property
    def typedefs(self):
        return self.some_children(TypeDef)

    @property
    def functions(self):
        return self.some_children(Function)

class TypeDef(TreeNode):
    def consume(self, tokens):
        if self.tokens or len(tokens) < 4:
            raise ParserError(tokens)
        self.tokens = tokens
        self.add_child(TypeName).consume([tokens[2]])
        tokens = tokens[3:]
        self.add_child(Type.class_for(tokens)).pop_consume(tokens)

class TypeName(Identifier):
    pass

class Type:
    @staticmethod
    def class_for(tokens):
        if tokens[0].text == "function":
            return FuncType
        else:
            return BasicType

class BasicType(Identifier, Type):
    def pop_consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = [tokens.pop(0)]

class FuncType(TreeNode, Type):
    def pop_consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = [tokens.pop(0)]
        self.add_child(ReturnTypes).pop_consume(tokens, lexer.OPAREN)
        assert tokens and isinstance(tokens[0], lexer.OPAREN)
        tokens.pop(0)
        self.add_child(ParamTypes).pop_consume(tokens, lexer.CPAREN)
        assert tokens and isinstance(tokens[0], lexer.CPAREN)
        tokens.pop(0)

    @property
    def returntypes(self):
        return self.one_child(ReturnTypes)

    @property
    def paramtypes(self):
        return self.one_child(ParamTypes)

class TypeList(TreeNode):
    def pop_consume(self, tokens, stop_at=None):
        self.tokens = copy.copy(tokens)
        while tokens:
            if stop_at is not None and isinstance(tokens[0], stop_at):
                break
            self.add_child(Type.class_for(tokens)).pop_consume(tokens)
            if tokens:
                if stop_at is not None and isinstance(tokens[0], stop_at):
                    break
                if not isinstance(tokens[0], lexer.COMMA):
                    raise ParserError(tokens)
                tokens.pop(0)
        else:
            if stop_at is not None:
                raise ParserError(tokens)

class ReturnTypes(TypeList):
    pass

class ParamTypes(TypeList):
    pass

class Function(TreeNode):
    def consume(self, tokens):
        if not self.tokens:
            if len(tokens) < 4:
                raise ParserError(tokens)
            self.tokens = tokens
            self.add_child(FullName).consume(tokens[1:4])
            tokens = tokens[4:]
            if tokens:
                if tokens[0].text != "returns":
                    raise ParserError(tokens)
                tokens.pop(0)
            self.add_child(ReturnTypes).pop_consume(tokens)
            self.add_child(UserParams)
            return

        if tokens[0].text == "argument":
            if not isinstance(self.latest_child, UserParams):
                raise ParserError(tokens)
        elif tokens[0].text in ("function", "symbol"):
            if isinstance(self.latest_child, Operations):
                raise ParserError(tokens)
            if not isinstance(self.latest_child, AutoParams):
                assert not isinstance(self.latest_child, Operations) # XXX?
                self.add_child(AutoParams)
        else:
            if not isinstance(self.latest_child, Operations):
                self.add_child(Operations)
        self.latest_child.consume(tokens)

    @property
    def name(self):
        return self.one_child(FullName)

    @property
    def returntypes(self):
        return self.one_child(ReturnTypes)

    @property
    def parameters(self):
        return self.some_children((UserParams, AutoParams))

    @property
    def operations(self):
        return self.one_child(Operations)

class FullName(TreeNode):
    def consume(self, tokens):
        if (self.tokens or len(tokens) != 3
            or not isinstance(tokens[1], lexer.DOUBLE_COLON)):
            raise ParserError(tokens)
        self.tokens = tokens
        self.add_child(Provider).consume([tokens[0]])
        self.add_child(ShortName).consume([tokens[2]])

    @property
    def provider(self):
        return self.one_child(Provider).name

    @property
    def shortname(self):
        return self.one_child(ShortName).name

    @property
    def ident(self):
        """How will the user refer to this item in the source?"""
        return "%s::%s" % (self.one_child(Provider).name,
                           self.one_child(ShortName).name)

class Provider(Identifier):
    pass

class ShortName(Identifier):
    pass

class UserParams(TreeNode):
    def consume(self, tokens):
        if not self.tokens:
            self.tokens = tokens
        self.add_child(Parameter).consume(tokens)

class TypeAndName(TreeNode):
    def consume(self, tokens, allow_fullname):
        self.add_child(Type.class_for(tokens)).pop_consume(tokens)
        if allow_fullname and len(tokens) == 3:
            klass = FullName
        elif len(tokens) == 1:
            klass = ShortName
        else:
            raise ParserError(self.tokens)
        self.add_child(klass).consume(tokens)

    @property
    def typename(self):
        return self.one_child(Type)

    @property
    def name(self):
        return self.one_child((ShortName, FullName))

class Parameter(TypeAndName):
    def consume(self, tokens):
        if self.tokens or len(tokens) < 3:
            raise ParserError(tokens)
        self.tokens = tokens
        TypeAndName.consume(self, tokens[1:], False)

class FuncRef(TypeAndName):
    def consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = tokens
        TypeAndName.consume(self, copy.copy(tokens), True)

class SymbolRef(TypeAndName):
    def consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = tokens
        TypeAndName.consume(
            self,
            [synthetic_token(tokens[0], "ptr")] + tokens[1:],
            True)

class AutoParams(TreeNode):
    CLASSES = {"function": FuncRef,
               "symbol": SymbolRef}

    def consume(self, tokens):
        self.add_child(self.CLASSES[tokens[0].text]).consume(tokens)

class Label(Identifier):
    def consume(self, tokens):
        Identifier.consume(self, [tokens[0]])

# Base mixin for all operations

class Operation:
    def consume(self, tokens):
        if self.tokens or len(tokens) != 1 + self.num_args:
            raise ParserError(tokens)
        self.tokens = tokens
        if self.num_args > 0:
            self.add_children(*tokens[1:])

    @property
    def operand(self):
        assert len(self.children) == 1
        return self.children[0]

# XXX blah blah blah

class TreeOp(TreeNode, Operation):
    pass

class NoArgOp(LeafNode, Operation):
    num_args = 0

class OneArgOp(TreeOp):
    num_args = 1

class TwoArgOp(TreeOp):
    num_args = 2

class JumpOp(OneArgOp):
    def add_children(self, target):
        self.add_child(Target).consume([target])

    @property
    def target(self):
        return self.one_child(Target)

class Target(Identifier):
    pass

class StackSlot(Integer):
    pass

# Classes which represent groups of operators in the parse tree

class SimpleOp(NoArgOp):
    @property
    def name(self):
        return self.tokens[0].text

class CompareOp(NoArgOp):
    pass

class CondBranchOp(JumpOp):
    pass

# Classes for operators that require specific individual parsing

class DerefOp(OneArgOp):
    def add_children(self, type):
        self.add_child(BasicType).pop_consume([type])

class GotoOp(JumpOp):
    pass

class NameOp(TwoArgOp):
    def add_children(self, slot, name):
        self.add_child(StackSlot).consume([slot])
        self.add_child(ShortName).consume([name])

    @property
    def slot(self):
        return self.one_child(StackSlot)

    @property
    def name(self):
        return self.one_child(ShortName)

class LoadOp(TreeOp):
    def consume(self, tokens):
        if self.tokens:
            raise ParserError(tokens)
        self.tokens = tokens
        if len(tokens) == 2:
            if isinstance(tokens[1], lexer.NUMBER):
                klass = Integer
            else:
                for klass in Pointer, Boolean:
                    if klass.VALUES.has_key(tokens[1].text):
                        break
                else:
                    klass = ShortName
        elif len(self.tokens) == 4:
            klass = FullName
        else:
            raise ParserError(tokens)
        self.add_child(klass).consume(tokens[1:])

    @property
    def named_operands(self):
        """Operands that need processing by the name annotator.
        """
        return self.some_children((ShortName, FullName))

    @property
    def typed_operands(self):
        """Operands that need processing by the type annotator.
        """
        return self.some_children(Constant)

class PickOp(OneArgOp):
    def add_children(self, slot):
        self.add_child(StackSlot).consume([slot])

class ReturnOp(NoArgOp):
    pass

# XXX

class Operations(TreeNode):
    CLASSES = {"deref": DerefOp,
               "goto": GotoOp,
               "name": NameOp,
               "load": LoadOp,
               "pick": PickOp,
               "return": ReturnOp}
    for op in ("abs", "add", "and", "div", "drop", "dup",
               "call", "mod", "mul", "neg", "not", "or",
               "over", "rot", "shl", "shr", "shra", "sub",
               "swap", "xor"):
        CLASSES[op] = SimpleOp
    for op in ("lt", "le", "eq", "ne", "ge", "gt"):
        CLASSES[op] = CompareOp
        CLASSES["b" + op] = CondBranchOp
    del op

    # Do not add an "addr" instruction for DW_OP_addr:
    #  a) The only address we can know is NULL, which we can do
    #     quite nicely with DW_OP_lit0.
    #  b) It will cause the bytecode to differ on 32- and 64-bit
    #     machines.  It currently doesn't, and that simplifies a
    #     lot of things.
    assert not CLASSES.has_key("addr")

    # Do not add a "bra" instruction, it gives no clue as to why
    # it would branch and makes code harder to read.  Users should
    # use "load NULL, bne" or "load 0, bne" and let the optimizer
    # figure it out.
    assert not CLASSES.has_key("bra")

    # Do not add "plus" or "minus" operations.  To calculate the
    # sum of two values you add them.  To calculate the difference
    # of two values you sub(tract) them.  That is all.
    assert not CLASSES.has_key("plus")
    assert not CLASSES.has_key("minus")

    def consume(self, tokens):
        if not self.tokens:
            self.tokens = tokens
        if len(tokens) == 2 and isinstance(tokens[1], lexer.COLON):
            klass = Label
        else:
            klass = self.CLASSES.get(tokens[0].text, None)
            if not klass:
                raise ParserError(tokens)
        self.add_child(klass).consume(tokens)

    @property
    def named_operations(self):
        """Operations that need processing by the name annotator.
        """
        return self.some_children((LoadOp, NameOp))

    @property
    def typed_operations(self):
        """Operations that need processing by the type annotator.
        """
        return self.some_children((DerefOp, LoadOp))

def build_tree(tokens):
    tree = TopLevel()
    try:
        group = None
        terminators = []
        while True:
            if group is None:
                group = []
                terminators.append(lexer.NEWLINE)
            try:
                token = tokens.next()
            except StopIteration:
                break
            if isinstance(token, terminators[-1]):
                terminators.pop()
                if not terminators:
                    tree.consume(group)
                    group = None
                    continue
            elif isinstance(token, lexer.OPAREN):
                terminators.append(lexer.CPAREN)
            if not isinstance(token, lexer.NEWLINE):
                group.append(token)
        assert not group
        return tree
    finally:
        debug_print("%s\n\n" % tree)
