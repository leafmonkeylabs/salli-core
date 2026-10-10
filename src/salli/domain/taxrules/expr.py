"""
The expression language rule sets are written in.

A rule set comes from a user or their AI agent, and an agent may have read
anything on the web while writing it. So expressions are data, never code:
they are tokenised and parsed here by hand into an immutable tree, and that tree
is evaluated by a small interpreter that can only do decimal arithmetic. Python's
`eval`, `compile` and `ast` are never involved, there are no loops, no recursion,
no attribute access and no host functions, and every expression is held to hard
size limits before it is parsed.

Grammar (lowest precedence first):

    expr     := or
    or       := and ("or" and)*
    and      := not ("and" not)*
    not      := "not" not | compare
    compare  := sum (("<" | "<=" | ">" | ">=" | "==" | "!=") sum)?   no chaining
    sum      := product (("+" | "-") product)*
    product  := unary (("*" | "/") unary)*
    unary    := "-" unary | atom
    atom     := NUMBER | "true" | "false" | REF | CALL | "(" expr ")"

- NUMBER is digits with an optional fraction, `_` allowed between digits
  (`1_800_000`, `0.15`). No exponents, no leading dot. At most 28 significant
  digits, so a literal is never silently rounded.
- REF is `role.<key>` (a ledger total by account tax role), `answer.<key>` (the
  user's answer to a question) or `line.<key>` (another line). Keys are
  `[a-z][a-z0-9_]*`; only line keys may have dotted parts, for the lines a
  building block compiles to (`line.general.band_1.tax`).
- Strings exist only where a function needs a name: a rounding mode, a band
  table, a choice's options. Their content is a key (`"nearest"`, `"joint"`).

Functions, the only ones there are:

    min(a, b, ...)  max(a, b, ...)  clamp(x, lo, hi)  abs(x)
    if(cond, then, else)                    only the chosen branch is evaluated
    round(x, "nearest"|"down"|"up"|"half_even", unit)
                                            to a multiple of unit, a positive
                                            number literal; "nearest" is
                                            ROUND_HALF_UP (ties away from zero),
                                            see arith.ROUNDING_MODES
    bands(amount, "table")                  tax on amount over a band table
    band_amount(amount, "table", n)         the part of amount in band n (1-based)
    choice(answer.x, "a", value_a, "b", value_b, ...)
                                            the value for the user's answer

Types are checked before anything is evaluated: numbers, booleans and choice
answers (strings) don't mix, `if` and `choice` branches agree, and a choice
answer can only be used by `choice`.
"""

from __future__ import annotations

import decimal
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Literal, cast

from salli.domain.taxrules.arith import (
    PRECISION,
    ROUNDING_MODES,
    BandTable,
    RoundingMode,
    decimal_context,
    round_to,
    significant_digits,
)

# ── limits ─────────────────────────────────────────────────────────────────────

MAX_LENGTH = 4_000
MAX_NODES = 1_000
#: How deeply operators, function calls and parentheses may nest.
MAX_DEPTH = 50
MAX_ARGUMENTS = 64

KEY_PATTERN = r"[a-z][a-z0-9_]*"
_KEY = re.compile(KEY_PATTERN)

Namespace = Literal["role", "answer", "line"]
NAMESPACES: tuple[Namespace, ...] = ("role", "answer", "line")

Value = Decimal | bool | str


# ── errors ─────────────────────────────────────────────────────────────────────


class ExprError(Exception):
    """Something wrong with an expression, and where: a 0-based `offset` into
    `text`, and the 1-based `line` and `column` people count in."""

    def __init__(self, message: str, text: str, offset: int) -> None:
        self.message = message
        self.text = text
        self.offset = max(0, min(offset, len(text)))
        before = text[: self.offset]
        self.line = before.count("\n") + 1
        self.column = self.offset - (before.rfind("\n") + 1) + 1
        super().__init__(f"{message} (line {self.line}, column {self.column})")

    @property
    def snippet(self) -> str:
        """The offending line with a caret under the column, trimmed to a
        window around it so a long expression stays readable."""
        source = self.text.split("\n")[self.line - 1] if self.text else ""
        start = max(0, self.column - 1 - 40)
        shown = source[start : start + 80]
        prefix = "…" if start > 0 else ""
        suffix = "…" if start + 80 < len(source) else ""
        caret = " " * (len(prefix) + self.column - 1 - start) + "^"
        return f"{prefix}{shown}{suffix}\n{caret}"


class ExprSyntaxError(ExprError):
    """Text that isn't an expression in this language."""


class ExprLimitError(ExprError):
    """An expression longer, larger or deeper than the limits allow."""


class ExprTypeError(ExprError):
    """An expression that parses but mixes types, or names something unknown."""


class ExprEvaluationError(ExprError):
    """An expression that failed while computing: division by zero, an answer
    no `choice` lists, a value too large to hold."""


# ── the tree ───────────────────────────────────────────────────────────────────
#
# Positions (`pos`, an offset into the text) don't take part in equality, so the
# tree for "a+b" equals the tree for "a + b" and `parse(unparse(e)) == e`.


@dataclass(frozen=True)
class Num:
    value: Decimal
    pos: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Bool:
    value: bool
    pos: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Str:
    value: str
    pos: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Ref:
    """A reference, which is also how a reference is identified: two `Ref`s
    with the same namespace and key are equal (and hash alike) wherever they
    appear."""

    namespace: Namespace
    key: str
    pos: int = field(default=0, compare=False)

    def __str__(self) -> str:
        return f"{self.namespace}.{self.key}"


UnaryOp = Literal["-", "not"]
BinaryOp = Literal["+", "-", "*", "/", "<", "<=", ">", ">=", "==", "!=", "and", "or"]


@dataclass(frozen=True)
class Unary:
    op: UnaryOp
    operand: Node
    pos: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Binary:
    op: BinaryOp
    left: Node
    right: Node
    pos: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple[Node, ...]
    pos: int = field(default=0, compare=False)


Node = Num | Bool | Str | Ref | Unary | Binary | Call


@dataclass(frozen=True)
class Expr:
    """A parsed expression: its tree, and the text it came from (for error
    locations). Equal when the trees are."""

    root: Node
    text: str = field(default="", compare=False)

    def __str__(self) -> str:
        return unparse(self)


class ExprType(Enum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING = "choice"  # only a choice question's answer is a string


# ── tokens ─────────────────────────────────────────────────────────────────────

_NUMBER = re.compile(r"[0-9]+(?:_[0-9]+)*(?:\.[0-9]+(?:_[0-9]+)*)?")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]*)*")
_STRING = re.compile(r'"([^"\n]*)"')
_OPERATORS = ("<=", ">=", "==", "!=", "+", "-", "*", "/", "<", ">", "(", ")", ",")
_WORDS = {"and", "or", "not", "true", "false"}

TokenKind = Literal["number", "string", "name", "ref", "op", "end"]


@dataclass(frozen=True)
class _Token:
    kind: TokenKind
    text: str
    pos: int


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if "0" <= c <= "9":
            m = _NUMBER.match(text, i)
            assert m is not None
            end = m.end()
            if end < n and (text[end].isalnum() or text[end] in "_."):
                raise ExprSyntaxError(
                    "A number is digits with an optional fraction, like 1_000 or 0.15",
                    text,
                    i,
                )
            tokens.append(_Token("number", m.group(0), i))
            i = end
            continue
        if c == '"':
            m = _STRING.match(text, i)
            if m is None:
                raise ExprSyntaxError("This string is never closed", text, i)
            if not _KEY.fullmatch(m.group(1)):
                raise ExprSyntaxError(
                    "A string names a mode, table or choice: lower-case letters, digits "
                    "and underscores, starting with a letter",
                    text,
                    i,
                )
            tokens.append(_Token("string", m.group(1), i))
            i = m.end()
            continue
        if c.isascii() and (c.isalpha() or c == "_"):
            m = _NAME.match(text, i)
            assert m is not None
            tokens.append(_classify_name(m.group(0), text, i))
            i = m.end()
            continue
        for op in _OPERATORS:
            if text.startswith(op, i):
                tokens.append(_Token("op", op, i))
                i += len(op)
                break
        else:
            raise ExprSyntaxError(f"Unexpected character {c!r}", text, i)
    tokens.append(_Token("end", "", n))
    return tokens


def _classify_name(word: str, text: str, pos: int) -> _Token:
    head, _, rest = word.partition(".")
    if head in NAMESPACES:
        if not rest:
            raise ExprSyntaxError(f"Expected {head}.<key>", text, pos)
        parts = rest.split(".")
        if head != "line" and len(parts) > 1:
            raise ExprSyntaxError(
                f"Only line references have dotted parts; {head}.<key> takes a single key",
                text,
                pos,
            )
        offset = pos + len(head) + 1
        for part in parts:
            if not _KEY.fullmatch(part):
                raise ExprSyntaxError(
                    f"{part!r} is not a key: keys are lower-case letters, digits and "
                    "underscores, starting with a letter",
                    text,
                    offset,
                )
            offset += len(part) + 1
        return _Token("ref", word, pos)
    if rest or "." in word:
        raise ExprSyntaxError(
            f"Unknown name {word!r}: a reference starts with role., answer. or line.",
            text,
            pos,
        )
    return _Token("name", word, pos)


# ── functions ──────────────────────────────────────────────────────────────────
#
# Each function's arguments, by kind. Literal kinds are fixed when the text is
# parsed (a mode, a table's name, a rounding unit, a band number, a choice's
# options), so the interpreter never has to decide what they mean at run time.

_Slot = Literal["expr", "mode", "table", "unit", "index", "answer", "option"]


@dataclass(frozen=True)
class _Signature:
    fixed: tuple[_Slot, ...]  # the leading arguments
    repeat: tuple[_Slot, ...] = ()  # then this group, `minimum`+ times
    minimum: int = 0


FUNCTIONS: dict[str, _Signature] = {
    "min": _Signature(("expr", "expr"), ("expr",)),
    "max": _Signature(("expr", "expr"), ("expr",)),
    "clamp": _Signature(("expr", "expr", "expr")),
    "abs": _Signature(("expr",)),
    "if": _Signature(("expr", "expr", "expr")),
    "round": _Signature(("expr", "mode", "unit")),
    "bands": _Signature(("expr", "table")),
    "band_amount": _Signature(("expr", "table", "index")),
    "choice": _Signature(("answer",), ("option", "expr"), minimum=1),
}

_USAGE = {
    "min": "min(a, b, ...)",
    "max": "max(a, b, ...)",
    "clamp": "clamp(x, lo, hi)",
    "abs": "abs(x)",
    "if": "if(condition, then, else)",
    "round": 'round(x, "nearest"|"down"|"up"|"half_even", unit)',
    "bands": 'bands(amount, "table")',
    "band_amount": 'band_amount(amount, "table", n)',
    "choice": 'choice(answer.x, "a", value_a, "b", value_b, ...)',
}


def _slot_for(sig: _Signature, index: int) -> _Slot | None:
    if index < len(sig.fixed):
        return sig.fixed[index]
    if not sig.repeat:
        return None
    return sig.repeat[(index - len(sig.fixed)) % len(sig.repeat)]


def _arity_ok(sig: _Signature, count: int) -> bool:
    extra = count - len(sig.fixed)
    if not sig.repeat:
        return extra == 0
    return extra >= sig.minimum * len(sig.repeat) and extra % len(sig.repeat) == 0


# ── parsing ────────────────────────────────────────────────────────────────────

_BINARY_POWER: dict[str, int] = {
    "or": 1,
    "and": 2,
    "<": 4,
    "<=": 4,
    ">": 4,
    ">=": 4,
    "==": 4,
    "!=": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
}
_NOT_POWER = 3
_COMPARE_POWER = 4
_NEGATE_POWER = 7
_ATOM_POWER = 8


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = _tokenize(text)
        self.i = 0
        self.nodes = 0
        self.nesting = 0
        # Each node's height, by identity, to hold the tree's depth to the limit
        # as it is built (a long `a + b + c + …` is deep without any nesting).
        self.heights: dict[int, int] = {}

    # tokens

    def peek(self) -> _Token:
        return self.tokens[self.i]

    def advance(self) -> _Token:
        token = self.tokens[self.i]
        if token.kind != "end":
            self.i += 1
        return token

    def expect_op(self, op: str, why: str) -> _Token:
        token = self.peek()
        if token.kind == "op" and token.text == op:
            return self.advance()
        raise ExprSyntaxError(why, self.text, token.pos)

    def error_at(self, token: _Token, message: str) -> ExprSyntaxError:
        return ExprSyntaxError(message, self.text, token.pos)

    # nodes

    def make[N: Node](self, node: N, *children: Node) -> N:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise ExprLimitError(
                f"An expression may have at most {MAX_NODES} parts", self.text, node.pos
            )
        height = 1 + max((self.heights[id(c)] for c in children), default=0)
        if height > MAX_DEPTH:
            raise ExprLimitError(
                f"An expression may nest at most {MAX_DEPTH} levels deep", self.text, node.pos
            )
        self.heights[id(node)] = height
        return node

    # grammar

    def parse(self) -> Node:
        node = self.expression(0)
        token = self.peek()
        if token.kind != "end":
            raise self.error_at(token, f"Unexpected {token.text!r} after a complete expression")
        return node

    def expression(self, min_power: int) -> Node:
        self.nesting += 1
        if self.nesting > MAX_DEPTH:
            raise ExprLimitError(
                f"An expression may nest at most {MAX_DEPTH} levels deep",
                self.text,
                self.peek().pos,
            )
        left = self.prefix()
        while True:
            token = self.peek()
            power = _BINARY_POWER.get(token.text) if token.kind in ("op", "name") else None
            if power is None or power <= min_power:
                break
            self.advance()
            right = self.expression(power)
            op = cast(BinaryOp, token.text)
            left = self.make(Binary(op, left, right, token.pos), left, right)
            if power == _COMPARE_POWER:
                after = self.peek()
                if after.kind == "op" and _BINARY_POWER.get(after.text) == _COMPARE_POWER:
                    raise self.error_at(after, "Comparisons can't be chained; join them with `and`")
        self.nesting -= 1
        return left

    def prefix(self) -> Node:
        token = self.advance()
        if token.kind == "number":
            return self.make(Num(_number(token, self.text), token.pos))
        if token.kind == "ref":
            namespace, _, key = token.text.partition(".")
            return self.make(Ref(cast(Namespace, namespace), key, token.pos))
        if token.kind == "string":
            raise self.error_at(
                token,
                "A string is only allowed as a rounding mode, a band table or a choice's option",
            )
        if token.kind == "op":
            if token.text == "(":
                inner = self.expression(0)
                self.expect_op(")", "Expected ')' to close this parenthesis")
                return inner
            if token.text == "-":
                operand = self.expression(_NEGATE_POWER - 1)
                return self.make(Unary("-", operand, token.pos), operand)
            if token.text in (")", ","):
                raise self.error_at(token, f"Expected a value before {token.text!r}")
            raise self.error_at(token, f"Expected a value, not {token.text!r}")
        if token.kind == "name":
            word = token.text
            if word == "true" or word == "false":
                return self.make(Bool(word == "true", token.pos))
            if word == "not":
                operand = self.expression(_NOT_POWER - 1)
                return self.make(Unary("not", operand, token.pos), operand)
            if word in ("and", "or"):
                raise self.error_at(token, f"Expected a value before {word!r}")
            if word in FUNCTIONS:
                return self.call(token)
            raise self.error_at(token, f"Unknown function or name {word!r}")
        raise self.error_at(token, "The expression ends too soon")

    def call(self, name: _Token) -> Node:
        sig = FUNCTIONS[name.text]
        self.expect_op("(", f"Expected '(' after {name.text}: {_USAGE[name.text]}")
        args: list[Node] = []
        if not (self.peek().kind == "op" and self.peek().text == ")"):
            while True:
                if len(args) >= MAX_ARGUMENTS:
                    raise ExprLimitError(
                        f"A function takes at most {MAX_ARGUMENTS} arguments",
                        self.text,
                        self.peek().pos,
                    )
                slot = _slot_for(sig, len(args))
                if slot is None:
                    raise self.error_at(self.peek(), f"Too many arguments; use {_USAGE[name.text]}")
                args.append(self.argument(name.text, slot))
                if self.peek().kind == "op" and self.peek().text == ",":
                    self.advance()
                    continue
                break
        self.expect_op(")", f"Expected ',' or ')' in {name.text}(…)")
        if not _arity_ok(sig, len(args)):
            raise self.error_at(name, f"Wrong number of arguments; use {_USAGE[name.text]}")
        if name.text == "choice":
            seen: set[str] = set()
            for arg in args[1::2]:
                assert isinstance(arg, Str)
                if arg.value in seen:
                    raise ExprSyntaxError(f"choice() lists {arg.value!r} twice", self.text, arg.pos)
                seen.add(arg.value)
        return self.make(Call(name.text, tuple(args), name.pos), *args)

    def argument(self, function: str, slot: _Slot) -> Node:
        token = self.peek()
        if slot in ("mode", "table", "option"):
            if token.kind != "string":
                what = {
                    "mode": 'a rounding mode in quotes: "nearest", "down", "up" or "half_even"',
                    "table": 'a band table\'s key in quotes, like "general"',
                    "option": 'one of the question\'s choices in quotes, like "single"',
                }[slot]
                raise self.error_at(token, f"{function}() expects {what} here")
            self.advance()
            if slot == "mode" and token.text not in ROUNDING_MODES:
                raise self.error_at(
                    token,
                    f"Unknown rounding mode {token.text!r}: use "
                    + ", ".join(f'"{m}"' for m in ROUNDING_MODES),
                )
            return self.make(Str(token.text, token.pos))
        node = self.expression(0)
        if slot == "unit" and not (isinstance(node, Num) and node.value > 0):
            raise self.error_at(
                token, "The rounding unit must be a positive number, like 1 or 0.01"
            )
        if slot == "index" and not (
            isinstance(node, Num)
            and node.value >= 1
            and node.value == node.value.to_integral_value()
        ):
            raise self.error_at(token, "The band number must be a whole number from 1")
        if slot == "answer" and not (isinstance(node, Ref) and node.namespace == "answer"):
            raise self.error_at(
                token, "choice() picks by an answer: its first argument is answer.<key>"
            )
        return node


def _number(token: _Token, text: str) -> Decimal:
    value = Decimal(token.text.replace("_", ""))
    if significant_digits(value) > PRECISION:
        raise ExprSyntaxError(
            f"A number may have at most {PRECISION} significant digits", text, token.pos
        )
    return value


def parse(text: str) -> Expr:
    """Parse `text`, or raise `ExprSyntaxError` / `ExprLimitError`."""
    if not isinstance(text, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ExprSyntaxError("An expression must be text", "", 0)
    if len(text) > MAX_LENGTH:
        raise ExprLimitError(
            f"An expression may be at most {MAX_LENGTH} characters", text, MAX_LENGTH
        )
    if not text.strip():
        raise ExprSyntaxError("The expression is empty", text, 0)
    return Expr(_Parser(text).parse(), text)


# ── walking and printing ───────────────────────────────────────────────────────


def _children(node: Node) -> tuple[Node, ...]:
    if isinstance(node, Unary):
        return (node.operand,)
    if isinstance(node, Binary):
        return (node.left, node.right)
    if isinstance(node, Call):
        return node.args
    return ()


def walk(expr: Expr | Node) -> Iterator[Node]:
    """Every node, parents before children, left to right."""
    stack: list[Node] = [expr.root if isinstance(expr, Expr) else expr]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(_children(node)))


def reference_nodes(expr: Expr) -> list[Ref]:
    """Every reference in order of appearance, with its position."""
    return [node for node in walk(expr) if isinstance(node, Ref)]


def references(expr: Expr) -> set[Ref]:
    """The distinct things `expr` refers to."""
    return set(reference_nodes(expr))


def _power(node: Node) -> int:
    if isinstance(node, Binary):
        return _BINARY_POWER[node.op]
    if isinstance(node, Unary):
        return _NEGATE_POWER if node.op == "-" else _NOT_POWER
    return _ATOM_POWER


def _print(node: Node) -> str:
    if isinstance(node, Num):
        return format(node.value, "f")
    if isinstance(node, Bool):
        return "true" if node.value else "false"
    if isinstance(node, Str):
        return f'"{node.value}"'
    if isinstance(node, Ref):
        return str(node)
    if isinstance(node, Unary):
        inner = _print(node.operand)
        if _power(node.operand) < _power(node):
            inner = f"({inner})"
        return f"-{inner}" if node.op == "-" else f"not {inner}"
    if isinstance(node, Binary):
        power = _BINARY_POWER[node.op]
        left = _print(node.left)
        right = _print(node.right)
        # Operators group to the left, and comparisons don't chain, so an equal
        # power needs parentheses on the right always, and on the left for a
        # comparison.
        if _power(node.left) < power or (power == _COMPARE_POWER and _power(node.left) == power):
            left = f"({left})"
        if _power(node.right) <= power:
            right = f"({right})"
        return f"{left} {node.op} {right}"
    return f"{node.name}({', '.join(_print(a) for a in node.args)})"


def unparse(expr: Expr | Node) -> str:
    """Canonical text for an expression, with only the parentheses it needs.
    `parse(unparse(e)) == e` for every parsed `e`."""
    return _print(expr.root if isinstance(expr, Expr) else expr)


# ── types ──────────────────────────────────────────────────────────────────────

_ARITHMETIC = {"+", "-", "*", "/"}
_ORDERING = {"<", "<=", ">", ">="}
_EQUALITY = {"==", "!="}
_LOGIC = {"and", "or"}


def type_of(expr: Expr, env_types: Mapping[Ref, ExprType]) -> ExprType:
    """The type `expr` produces, given the type of everything it may refer to,
    or `ExprTypeError` at the first mistake."""
    text = expr.text

    def fail(node: Node, message: str) -> ExprTypeError:
        return ExprTypeError(message, text, node.pos)

    def want(node: Node, expected: ExprType, what: str) -> None:
        got = check(node)
        if got is not expected:
            raise fail(node, f"{what} must be a {expected.value}, not a {got.value}")

    def check(node: Node) -> ExprType:
        if isinstance(node, Num):
            return ExprType.NUMBER
        if isinstance(node, Bool):
            return ExprType.BOOLEAN
        if isinstance(node, Str):
            raise fail(node, "A string can't be used as a value")
        if isinstance(node, Ref):
            found = env_types.get(node)
            if found is None:
                raise fail(node, f"Unknown reference {node}")
            if found is ExprType.STRING:
                raise fail(node, f"{node} is a choice; use it as choice()'s first argument")
            return found
        if isinstance(node, Unary):
            if node.op == "-":
                want(node.operand, ExprType.NUMBER, "What '-' negates")
                return ExprType.NUMBER
            want(node.operand, ExprType.BOOLEAN, "What 'not' negates")
            return ExprType.BOOLEAN
        if isinstance(node, Binary):
            if node.op in _ARITHMETIC or node.op in _ORDERING:
                want(node.left, ExprType.NUMBER, f"Each side of '{node.op}'")
                want(node.right, ExprType.NUMBER, f"Each side of '{node.op}'")
                return ExprType.NUMBER if node.op in _ARITHMETIC else ExprType.BOOLEAN
            if node.op in _LOGIC:
                want(node.left, ExprType.BOOLEAN, f"Each side of '{node.op}'")
                want(node.right, ExprType.BOOLEAN, f"Each side of '{node.op}'")
                return ExprType.BOOLEAN
            left, right = check(node.left), check(node.right)
            if left is not right:
                raise fail(node, f"'{node.op}' compares a {left.value} with a {right.value}")
            return ExprType.BOOLEAN
        return check_call(node)

    def check_call(node: Call) -> ExprType:
        name, args = node.name, node.args
        if name in ("min", "max", "clamp", "abs"):
            for arg in args:
                want(arg, ExprType.NUMBER, f"Each argument of {name}()")
            return ExprType.NUMBER
        if name == "if":
            want(args[0], ExprType.BOOLEAN, "if()'s condition")
            return same_type(node, args[1:], "if()'s two branches")
        if name in ("round", "bands", "band_amount"):
            want(args[0], ExprType.NUMBER, f"The amount {name}() works on")
            return ExprType.NUMBER
        # choice
        answer = args[0]
        found = env_types.get(answer) if isinstance(answer, Ref) else None
        if found is None:
            raise fail(answer, f"Unknown reference {unparse(answer)}")
        if found is not ExprType.STRING:
            raise fail(
                answer, f"choice() needs a choice question's answer; {unparse(answer)} isn't one"
            )
        return same_type(node, args[2::2], "choice()'s values")

    def same_type(node: Node, branches: tuple[Node, ...], what: str) -> ExprType:
        types = [check(b) for b in branches]
        if any(t is not types[0] for t in types):
            raise fail(node, f"{what} must all be the same type")
        return types[0]

    return check(expr.root)


# ── evaluation ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Scope:
    """What an evaluation can see: a value for each reference, and the rule
    set's band tables by key."""

    values: Mapping[Ref, Value]
    tables: Mapping[str, BandTable] = field(default_factory=dict[str, BandTable])


def evaluate(expr: Expr, scope: Scope) -> Decimal | bool:
    """The value of `expr`, computed in the rule-set decimal context (28 digits,
    errors trapped), so the same inputs always give the same result.

    Raises `ExprEvaluationError` with the location of the part that failed.
    Types are checked again as values are used, so an expression that was never
    type-checked fails cleanly too.
    """
    text = expr.text

    def fail(node: Node, message: str) -> ExprEvaluationError:
        return ExprEvaluationError(message, text, node.pos)

    def number(node: Node) -> Decimal:
        value = run(node)
        if isinstance(value, Decimal):
            return value
        raise fail(node, "Expected a number here")

    def boolean(node: Node) -> bool:
        value = run(node)
        if isinstance(value, bool):
            return value
        raise fail(node, "Expected true or false here")

    def lookup(node: Ref) -> Value:
        if node not in scope.values:
            raise fail(node, f"No value for {node}")
        value = scope.values[node]
        if isinstance(value, Decimal) and not value.is_finite():
            raise fail(node, f"{node} is not a finite number")
        if not isinstance(value, Decimal | bool | str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise fail(node, f"{node} has a value of an unsupported kind")
        return value

    def table(node: Node) -> BandTable:
        assert isinstance(node, Str)
        found = scope.tables.get(node.value)
        if found is None:
            raise fail(node, f"There is no band table {node.value!r}")
        return found

    def run(node: Node) -> Decimal | bool:
        try:
            return dispatch(node)
        except ExprEvaluationError:
            raise
        except (ArithmeticError, ValueError) as error:
            # decimal's signals (InvalidOperation, DivisionByZero, Overflow) are
            # ArithmeticErrors; arith raises ValueError for a missing band.
            raise fail(node, _describe(error)) from None

    def dispatch(node: Node) -> Decimal | bool:
        if isinstance(node, Num | Bool):
            return node.value
        if isinstance(node, Str):
            raise fail(node, "A string can't be used as a value")
        if isinstance(node, Ref):
            value = lookup(node)
            if isinstance(value, str):
                raise fail(node, f"{node} is a choice; use it as choice()'s first argument")
            return value
        if isinstance(node, Unary):
            return -number(node.operand) if node.op == "-" else not boolean(node.operand)
        if isinstance(node, Binary):
            return binary(node)
        return call(node)

    def binary(node: Binary) -> Decimal | bool:
        op = node.op
        if op == "and":
            return boolean(node.left) and boolean(node.right)
        if op == "or":
            return boolean(node.left) or boolean(node.right)
        if op in _EQUALITY:
            left, right = run(node.left), run(node.right)
            if isinstance(left, bool) != isinstance(right, bool):
                raise fail(node, f"'{op}' compares a number with true/false")
            return (left == right) if op == "==" else (left != right)
        left, right = number(node.left), number(node.right)
        operations: dict[str, Callable[[Decimal, Decimal], Decimal | bool]] = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
        }
        return operations[op](left, right)

    def call(node: Call) -> Decimal | bool:
        name, args = node.name, node.args
        if name == "min":
            return min(number(a) for a in args)
        if name == "max":
            return max(number(a) for a in args)
        if name == "abs":
            return abs(number(args[0]))
        if name == "clamp":
            x, lo, hi = (number(a) for a in args)
            if lo > hi:
                raise fail(node, f"clamp()'s lower bound {lo} is above its upper bound {hi}")
            return min(max(x, lo), hi)
        if name == "if":
            return run(args[1]) if boolean(args[0]) else run(args[2])
        if name == "round":
            mode, unit = args[1], args[2]
            assert isinstance(mode, Str) and isinstance(unit, Num)
            return round_to(number(args[0]), cast(RoundingMode, mode.value), unit.value)
        if name == "bands":
            return table(args[1]).tax(number(args[0]))
        if name == "band_amount":
            index = args[2]
            assert isinstance(index, Num)
            found = table(args[1])
            n = int(index.value)
            if n > len(found.bands):
                raise fail(
                    index, f"Band {n} doesn't exist; {unparse(args[1])} has {len(found.bands)}"
                )
            return found.amount_in_band(number(args[0]), n)
        # choice
        answer = args[0]
        assert isinstance(answer, Ref)
        picked = lookup(answer)
        if not isinstance(picked, str):
            raise fail(answer, f"{answer} is not a choice question's answer")
        for option, value in zip(args[1::2], args[2::2], strict=True):
            assert isinstance(option, Str)
            if option.value == picked:
                return run(value)
        raise fail(answer, f"{answer} is {picked!r}, which this choice() doesn't list")

    with decimal_context():
        return run(expr.root)


def _describe(error: BaseException) -> str:
    if isinstance(error, decimal.DivisionByZero):
        return "Division by zero"
    if isinstance(error, decimal.Overflow):
        return "A value grew too large to hold"
    if isinstance(error, decimal.InvalidOperation):
        # decimal's own signals carry a list of condition classes, not words;
        # arith.round_to raises with a sentence.
        if error.args and isinstance(error.args[0], str):
            return error.args[0]
        return "An undefined calculation, such as 0/0, or a value too large to round exactly"
    return str(error) or type(error).__name__
