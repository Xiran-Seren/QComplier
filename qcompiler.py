#!/usr/bin/env python3
"""QCompiler: QL -> tokens/QAST/QTAC/ARM64.

This implementation targets the QL subset used by the supplied qsort sample.
It uses a recursive-descent parser, then emits simple three-address code and
AArch64 GNU assembler source.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


KEYWORDS = {"int", "void", "if", "else", "while", "return"}
TWO_CHAR_OPS = {"<=", ">=", "==", "!=", "&&", "||", "+=", "-=", "*=", "/="}
ONE_CHAR = set("{}()[];,+-*/%=<>!")


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int

    def text(self) -> str:
        return f"({self.kind}, {self.value})"


def normalize_source(text: str) -> str:
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\uff1b", ";")
        .replace("\uff0c", ",")
        .replace("\uff08", "(")
        .replace("\uff09", ")")
    )


def lex(text: str) -> list[Token]:
    text = normalize_source(text)
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1

    def advance(n: int = 1) -> str:
        nonlocal i, line, col
        chunk = text[i : i + n]
        for ch in chunk:
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1
        i += n
        return chunk

    while i < len(text):
        ch = text[i]
        if ch.isspace():
            advance()
            continue
        if text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                advance()
            continue
        if text.startswith("/*", i):
            advance(2)
            while i < len(text) and not text.startswith("*/", i):
                advance()
            if i >= len(text):
                raise SyntaxError("Unterminated block comment")
            advance(2)
            continue
        start_line, start_col = line, col
        if ch.isalpha() or ch == "_":
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[i:])
            assert m
            value = advance(len(m.group(0)))
            kind = "KEYWORD" if value in KEYWORDS else "ID"
            tokens.append(Token(kind, value, start_line, start_col))
            continue
        if ch.isdigit():
            m = re.match(r"[0-9]+", text[i:])
            assert m
            tokens.append(Token("INT", advance(len(m.group(0))), start_line, start_col))
            continue
        two = text[i : i + 2]
        if two in TWO_CHAR_OPS:
            tokens.append(Token("OP", advance(2), start_line, start_col))
            continue
        if ch in ONE_CHAR:
            kind = "OP" if ch in "+-*/%=<>!" else "PUNC"
            tokens.append(Token(kind, advance(), start_line, start_col))
            continue
        raise SyntaxError(f"Unknown character {ch!r} at {line}:{col}")
    tokens.append(Token("EOF", "EOF", line, col))
    return tokens


@dataclass
class Node:
    kind: str
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "attrs": self.attrs,
            "children": [child.to_dict() for child in self.children],
        }


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def cur(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        return self.tokens[self.pos + offset]

    def accept(self, value: str | None = None, kind: str | None = None) -> Token | None:
        tok = self.cur()
        if value is not None and tok.value != value:
            return None
        if kind is not None and tok.kind != kind:
            return None
        self.pos += 1
        return tok

    def expect(self, value: str | None = None, kind: str | None = None) -> Token:
        tok = self.accept(value, kind)
        if tok is None:
            want = value if value is not None else kind
            got = self.cur()
            raise SyntaxError(f"Expected {want}, got {got.value!r} at {got.line}:{got.col}")
        return tok

    def parse(self) -> Node:
        self.expect("{")
        items: list[Node] = []
        while not self.accept("}"):
            if self.cur().value in {"int", "void"}:
                items.append(self.parse_decl_or_func())
            else:
                items.append(self.parse_stmt())
        self.expect(kind="EOF")
        return Node("Program", children=items)

    def parse_type(self) -> str:
        return self.expect(kind="KEYWORD").value

    def parse_decl_or_func(self) -> Node:
        typ = self.parse_type()
        name = self.expect(kind="ID").value
        if self.accept("("):
            params = self.parse_params()
            body = self.parse_block()
            return Node("Function", {"name": name, "type": typ, "params": params}, [body])
        dims = self.parse_array_suffix()
        self.expect(";")
        return Node("Decl", {"name": name, "type": typ, "dims": dims})

    def parse_params(self) -> list[dict[str, Any]]:
        params: list[dict[str, Any]] = []
        if self.accept(")"):
            return params
        while True:
            typ = self.parse_type()
            name = self.expect(kind="ID").value
            is_array = False
            if self.accept("["):
                self.expect("]")
                is_array = True
            params.append({"type": typ, "name": name, "array": is_array})
            if self.accept(")"):
                break
            if self.accept(";") or self.accept(","):
                if self.accept(")"):
                    break
                continue
            self.expect(")")
        return params

    def parse_array_suffix(self) -> list[int]:
        dims: list[int] = []
        while self.accept("["):
            size = int(self.expect(kind="INT").value)
            self.expect("]")
            dims.append(size)
        return dims

    def parse_block(self) -> Node:
        self.expect("{")
        items: list[Node] = []
        while not self.accept("}"):
            if self.cur().value in {"int", "void"}:
                items.append(self.parse_decl_or_func())
            else:
                items.append(self.parse_stmt())
        return Node("Block", children=items)

    def parse_stmt(self) -> Node:
        if self.accept(";"):
            return Node("Nop")
        if self.cur().value == "{":
            return self.parse_block()
        if self.accept("if"):
            self.expect("(")
            cond = self.parse_expr()
            self.expect(")")
            then = self.parse_stmt()
            if self.accept("else"):
                return Node("If", children=[cond, then, self.parse_stmt()])
            return Node("If", children=[cond, then])
        if self.accept("while"):
            self.expect("(")
            cond = self.parse_expr()
            self.expect(")")
            return Node("While", children=[cond, self.parse_stmt()])
        if self.accept("return"):
            expr = self.parse_expr()
            self.expect(";")
            return Node("Return", children=[expr])
        expr = self.parse_expr()
        self.expect(";")
        return Node("ExprStmt", children=[expr])

    def parse_expr(self) -> Node:
        return self.parse_assignment()

    def parse_assignment(self) -> Node:
        left = self.parse_logical_or()
        if self.cur().value in {"=", "+=", "-=", "*=", "/="}:
            op = self.cur().value
            self.pos += 1
            right = self.parse_assignment()
            return Node("Assign", {"op": op}, [left, right])
        return left

    def parse_logical_or(self) -> Node:
        node = self.parse_logical_and()
        while self.accept("||"):
            node = Node("Binary", {"op": "||"}, [node, self.parse_logical_and()])
        return node

    def parse_logical_and(self) -> Node:
        node = self.parse_equality()
        while self.accept("&&"):
            node = Node("Binary", {"op": "&&"}, [node, self.parse_equality()])
        return node

    def parse_equality(self) -> Node:
        node = self.parse_rel()
        while self.cur().value in {"==", "!="}:
            op = self.cur().value
            self.pos += 1
            node = Node("Binary", {"op": op}, [node, self.parse_rel()])
        return node

    def parse_rel(self) -> Node:
        node = self.parse_add()
        while self.cur().value in {"<", "<=", ">", ">="}:
            op = self.cur().value
            self.pos += 1
            node = Node("Binary", {"op": op}, [node, self.parse_add()])
        return node

    def parse_add(self) -> Node:
        node = self.parse_mul()
        while self.cur().value in {"+", "-"}:
            op = self.cur().value
            self.pos += 1
            node = Node("Binary", {"op": op}, [node, self.parse_mul()])
        return node

    def parse_mul(self) -> Node:
        node = self.parse_unary()
        while self.cur().value in {"*", "/"}:
            op = self.cur().value
            self.pos += 1
            node = Node("Binary", {"op": op}, [node, self.parse_unary()])
        return node

    def parse_unary(self) -> Node:
        if self.cur().value in {"!", "-"}:
            op = self.cur().value
            self.pos += 1
            return Node("Unary", {"op": op}, [self.parse_unary()])
        return self.parse_primary()

    def parse_primary(self) -> Node:
        if tok := self.accept(kind="INT"):
            return Node("Int", {"value": int(tok.value)})
        if tok := self.accept(kind="ID"):
            name = tok.value
            if self.accept("("):
                args = self.parse_args()
                return Node("Call", {"name": name}, args)
            node = Node("Var", {"name": name})
            while self.accept("["):
                if self.accept("]"):
                    node = Node("ArrayDecay", children=[node])
                else:
                    idx = self.parse_expr()
                    self.expect("]")
                    node = Node("Index", children=[node, idx])
            return node
        if self.accept("("):
            node = self.parse_expr()
            self.expect(")")
            return node
        tok = self.cur()
        raise SyntaxError(f"Expected expression, got {tok.value!r} at {tok.line}:{tok.col}")

    def parse_args(self) -> list[Node]:
        args: list[Node] = []
        if self.accept(")"):
            return args
        while True:
            args.append(self.parse_expr())
            if self.accept(")"):
                break
            self.expect(",")
            if self.accept(")"):
                break
        return args


class TacEmitter:
    def __init__(self):
        self.temp_id = 0
        self.label_id = 0
        self.lines: list[str] = []
        self.symbols: list[dict[str, Any]] = []
        self.scopes: list[set[str]] = [set()]
        self.functions: dict[str, dict[str, Any]] = {}

    def temp(self) -> str:
        value = f"t{self.temp_id}"
        self.temp_id += 1
        return value

    def label(self) -> str:
        value = f"l{self.label_id}"
        self.label_id += 1
        return value

    def emit_program(self, node: Node) -> tuple[str, list[dict[str, Any]]]:
        for child in node.children:
            if child.kind == "Decl":
                self.emit_global_decl(child)
        for child in node.children:
            if child.kind == "Function":
                self.emit_function(child)
        for child in node.children:
            if child.kind not in {"Decl", "Function"}:
                self.emit_stmt(child)
        return "\n".join(self.lines) + "\n", self.symbols

    def emit_global_decl(self, node: Node) -> None:
        name = node.attrs["name"]
        dims = node.attrs["dims"]
        count = 1
        for dim in dims:
            count *= dim
        width = count * 8
        self.symbols.append({"scope": "global", "name": name, "type": node.attrs["type"], "dims": dims, "width": width})
        self.lines.append(f"i{width} {name};")

    def emit_function(self, node: Node) -> None:
        name = node.attrs["name"]
        params = node.attrs["params"]
        self.functions[name] = {"params": params, "return": node.attrs["type"]}
        self.lines.append(f"define {name}({', '.join(p['name'] for p in params)}){{")
        self.lines.append(f"LABEL {name};")
        self.scopes.append(set(p["name"] for p in params))
        for p in params:
            self.symbols.append({"scope": name, "name": p["name"], "type": p["type"], "param": True, "array": p["array"], "width": 8})
        self.emit_stmt(node.children[0])
        self.lines.append("RETURN 0;")
        self.lines.append("}")
        self.scopes.pop()

    def emit_decl(self, node: Node) -> None:
        name = node.attrs["name"]
        dims = node.attrs["dims"]
        count = 1
        for dim in dims:
            count *= dim
        width = max(1, count) * 8
        self.scopes[-1].add(name)
        scope = "global" if len(self.scopes) == 1 else "local"
        self.symbols.append({"scope": scope, "name": name, "type": node.attrs["type"], "dims": dims, "width": width})

    def emit_stmt(self, node: Node) -> None:
        if node.kind == "Nop":
            self.lines.append("NOP;")
        elif node.kind == "Decl":
            self.emit_decl(node)
        elif node.kind == "Block":
            self.scopes.append(set())
            for child in node.children:
                self.emit_stmt(child)
            self.scopes.pop()
        elif node.kind == "ExprStmt":
            self.emit_expr(node.children[0])
        elif node.kind == "Return":
            value = self.emit_expr(node.children[0])
            self.lines.append(f"RETURN {value};")
        elif node.kind == "If":
            else_label = self.label()
            end_label = self.label()
            self.emit_branch(node.children[0], else_label, invert=True)
            self.emit_stmt(node.children[1])
            if len(node.children) == 3:
                self.lines.append(f"GOTO {end_label};")
                self.lines.append(f"LABEL {else_label};")
                self.emit_stmt(node.children[2])
                self.lines.append(f"LABEL {end_label};")
            else:
                self.lines.append(f"LABEL {else_label};")
        elif node.kind == "While":
            start = self.label()
            end = self.label()
            self.lines.append(f"LABEL {start};")
            self.emit_branch(node.children[0], end, invert=True)
            self.emit_stmt(node.children[1])
            self.lines.append(f"GOTO {start};")
            self.lines.append(f"LABEL {end};")
        else:
            raise NotImplementedError(node.kind)

    def emit_branch(self, cond: Node, false_label: str, invert: bool = False) -> None:
        if cond.kind == "Binary" and cond.attrs["op"] in {"<", "<=", ">", ">=", "==", "!="}:
            left = self.emit_expr(cond.children[0])
            right = self.emit_expr(cond.children[1])
            true_label = self.label()
            self.lines.append(f"IF {left} {cond.attrs['op']} {right} THEN {true_label} ELSE {false_label};")
            self.lines.append(f"LABEL {true_label};")
            return
        value = self.emit_expr(cond)
        true_label = self.label()
        self.lines.append(f"IF {value} != 0 THEN {true_label} ELSE {false_label};")
        self.lines.append(f"LABEL {true_label};")

    def emit_expr(self, node: Node) -> str:
        if node.kind == "Int":
            return str(node.attrs["value"])
        if node.kind == "Var":
            return node.attrs["name"]
        if node.kind == "ArrayDecay":
            return self.base_name(node.children[0])
        if node.kind == "Index":
            addr = self.emit_addr(node)
            out = self.temp()
            self.lines.append(f"{out} = M[{addr}];")
            return out
        if node.kind == "Assign":
            return self.emit_assign(node)
        if node.kind == "Unary":
            value = self.emit_expr(node.children[0])
            out = self.temp()
            if node.attrs["op"] == "-":
                self.lines.append(f"{out} = 0 - {value};")
            else:
                self.lines.append(f"{out} = {value} == 0;")
            return out
        if node.kind == "Binary":
            left = self.emit_expr(node.children[0])
            right = self.emit_expr(node.children[1])
            out = self.temp()
            self.lines.append(f"{out} = {left} {node.attrs['op']} {right};")
            return out
        if node.kind == "Call":
            for arg in node.children:
                self.lines.append(f"PAR {self.emit_arg(arg)};")
            out = self.temp()
            self.lines.append(f"{out} = CALL {node.attrs['name']}, {len(node.children)};")
            return out
        raise NotImplementedError(node.kind)

    def emit_arg(self, node: Node) -> str:
        if node.kind in {"Var", "ArrayDecay"}:
            return self.base_name(node)
        return self.emit_expr(node)

    def emit_assign(self, node: Node) -> str:
        left, right = node.children
        rhs = self.emit_expr(right)
        op = node.attrs["op"]
        if op != "=":
            cur = self.emit_expr(left)
            tmp = self.temp()
            self.lines.append(f"{tmp} = {cur} {op[0]} {rhs};")
            rhs = tmp
        if left.kind == "Index":
            addr = self.emit_addr(left)
            self.lines.append(f"M[{addr}] = {rhs};")
        elif left.kind == "Var":
            self.lines.append(f"{left.attrs['name']} = {rhs};")
        else:
            raise SyntaxError("Left side of assignment is not assignable")
        return rhs

    def emit_addr(self, node: Node) -> str:
        base = self.emit_arg(node.children[0])
        idx = self.emit_expr(node.children[1])
        scaled = self.temp()
        out = self.temp()
        self.lines.append(f"{scaled} = {idx} * 8;")
        self.lines.append(f"{out} = {base} + {scaled};")
        return out

    def base_name(self, node: Node) -> str:
        while node.kind == "ArrayDecay":
            node = node.children[0]
        if node.kind == "Var":
            return node.attrs["name"]
        if node.kind == "Index":
            return self.emit_addr(node)
        raise SyntaxError("Expected addressable value")


class ArmGenerator:
    def __init__(self, tac: str):
        self.tac_lines = [line.strip() for line in tac.splitlines() if line.strip()]
        self.globals: dict[str, int] = {}
        self.functions: dict[str, list[str]] = {}
        self.main_lines: list[str] = []
        self.pending_params: list[str] = []

    def parse(self) -> None:
        current: str | None = None
        for line in self.tac_lines:
            if m := re.fullmatch(r"i(\d+)\s+([A-Za-z_][A-Za-z0-9_]*);", line):
                self.globals[m.group(2)] = int(m.group(1))
            elif m := re.fullmatch(r"define\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)\{", line):
                current = m.group(1)
                params = [p.strip() for p in m.group(2).split(",") if p.strip()]
                self.functions[current] = [f";@params {','.join(params)}"]
            elif line == "}":
                current = None
            elif current:
                self.functions[current].append(line)
            else:
                self.main_lines.append(line)

    def generate(self) -> str:
        self.parse()
        out: list[str] = [
            ".arch armv8-a",
            ".section .bss",
            ".align 3",
        ]
        for name, width in self.globals.items():
            out += [f".global {name}", f"{name}:", f"    .zero {width}"]
        out += [".section .text", ".global _start"]
        for name, lines in self.functions.items():
            out.extend(self.emit_function(name, lines))
        out += ["_start:"]
        ctx = self.context_for(self.main_lines, [])
        out.extend(self.emit_lines(self.main_lines, ctx, "_exit"))
        out += ["_exit:", "    mov x0, #0", "    mov x8, #93", "    svc #0"]
        return "\n".join(out) + "\n"

    def emit_function(self, name: str, lines: list[str]) -> list[str]:
        params: list[str] = []
        body = lines
        if lines and lines[0].startswith(";@params "):
            params = [p for p in lines[0][9:].split(",") if p]
            body = lines[1:]
        if body and body[0].rstrip(";") == f"LABEL {name}":
            body = body[1:]
        ctx = self.context_for(body, params)
        frame = align16(8 * len(ctx["locals"]))
        out = [
            f"{name}:",
            "    stp x29, x30, [sp, #-16]!",
            "    mov x29, sp",
            f"    sub sp, sp, #{frame}",
        ]
        for i, p in enumerate(params[:8]):
            out.append(f"    str x{i}, [x29, #-{ctx['locals'][p]}]")
        out.extend(self.emit_lines(body, ctx, f".L{name}_exit"))
        out += [
            f".L{name}_exit:",
            f"    add sp, sp, #{frame}",
            "    ldp x29, x30, [sp], #16",
            "    ret",
        ]
        return out

    def context_for(self, lines: list[str], params: list[str]) -> dict[str, Any]:
        names = set(params)
        for line in lines:
            for name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", line):
                if name not in {"LABEL", "GOTO", "IF", "THEN", "ELSE", "PAR", "CALL", "RETURN", "M", "NOP"}:
                    if not name.startswith("l") and name not in self.globals and name not in self.functions:
                        names.add(name)
        locals_map = {name: (i + 1) * 8 for i, name in enumerate(sorted(names))}
        return {"locals": locals_map}

    def emit_lines(self, lines: list[str], ctx: dict[str, Any], exit_label: str) -> list[str]:
        out: list[str] = []
        self.pending_params = []
        for raw in lines:
            line = raw.rstrip(";")
            if line.startswith(";@") or line == "NOP":
                continue
            if line.startswith("LABEL "):
                out.append(f"{line.split()[1]}:")
            elif line.startswith("GOTO "):
                out.append(f"    b {line.split()[1]}")
            elif line.startswith("PAR "):
                self.pending_params.append(line[4:].strip())
            elif m := re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*CALL\s+([A-Za-z_][A-Za-z0-9_]*),\s*(\d+)", line):
                dest, fn, _argc = m.groups()
                for i, arg in enumerate(self.pending_params[:8]):
                    out.extend(self.load_value(arg, "x9", ctx))
                    out.append(f"    mov x{i}, x9")
                self.pending_params = []
                out.append(f"    bl {fn}")
                out.extend(self.store_value("x0", dest, ctx))
            elif m := re.fullmatch(r"RETURN\s+(.+)", line):
                out.extend(self.load_value(m.group(1), "x0", ctx))
                out.append(f"    b {exit_label}")
            elif m := re.fullmatch(r"IF\s+(.+?)\s+(<=|>=|==|!=|<|>)\s+(.+?)\s+THEN\s+(\w+)\s+ELSE\s+(\w+)", line):
                left, op, right, lt, lf = m.groups()
                out.extend(self.load_value(left, "x9", ctx))
                out.extend(self.load_value(right, "x10", ctx))
                out.append("    cmp x9, x10")
                out.append(f"    {branch_op(op)} {lt}")
                out.append(f"    b {lf}")
            elif m := re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*M\[(.+)\]", line):
                dest, addr = m.groups()
                out.extend(self.load_value(addr, "x9", ctx))
                out.append("    ldr x10, [x9]")
                out.extend(self.store_value("x10", dest, ctx))
            elif m := re.fullmatch(r"M\[(.+)\]\s*=\s*(.+)", line):
                addr, value = m.groups()
                out.extend(self.load_value(addr, "x9", ctx))
                out.extend(self.load_value(value, "x10", ctx))
                out.append("    str x10, [x9]")
            elif m := re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*([+\-*/]|<=|>=|==|!=|<|>|&&|\|\|)\s*(.+)", line):
                dest, left, op, right = m.groups()
                out.extend(self.load_value(left, "x9", ctx))
                out.extend(self.load_value(right, "x10", ctx))
                out.extend(self.binary_op(op, "x11"))
                out.extend(self.store_value("x11", dest, ctx))
            elif m := re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line):
                dest, src = m.groups()
                out.extend(self.load_value(src, "x9", ctx))
                out.extend(self.store_value("x9", dest, ctx))
            else:
                out.append(f"    // unsupported TAC: {line}")
        return out

    def binary_op(self, op: str, target: str) -> list[str]:
        if op == "+":
            return [f"    add {target}, x9, x10"]
        if op == "-":
            return [f"    sub {target}, x9, x10"]
        if op == "*":
            return [f"    mul {target}, x9, x10"]
        if op == "/":
            return [f"    sdiv {target}, x9, x10"]
        if op in {"<", "<=", ">", ">=", "==", "!="}:
            return ["    cmp x9, x10", f"    cset {target}, {cond_op(op)}"]
        if op == "&&":
            return ["    cmp x9, #0", "    cset x9, ne", "    cmp x10, #0", "    cset x10, ne", f"    and {target}, x9, x10"]
        if op == "||":
            return ["    orr x9, x9, x10", "    cmp x9, #0", f"    cset {target}, ne"]
        raise NotImplementedError(op)

    def load_value(self, operand: str, reg: str, ctx: dict[str, Any]) -> list[str]:
        operand = operand.strip()
        if re.fullmatch(r"-?\d+", operand):
            return [f"    mov {reg}, #{operand}"]
        if operand in self.globals:
            return [f"    adrp {reg}, {operand}", f"    add {reg}, {reg}, :lo12:{operand}"]
        if operand in ctx["locals"]:
            return [f"    ldr {reg}, [x29, #-{ctx['locals'][operand]}]"]
        return [f"    mov {reg}, #0    // unknown operand {operand}"]

    def store_value(self, reg: str, name: str, ctx: dict[str, Any]) -> list[str]:
        if name in ctx["locals"]:
            return [f"    str {reg}, [x29, #-{ctx['locals'][name]}]"]
        if name in self.globals:
            return [f"    adrp x16, {name}", f"    add x16, x16, :lo12:{name}", f"    str {reg}, [x16]"]
        return [f"    // unknown store target {name}"]


def align16(value: int) -> int:
    return (value + 15) // 16 * 16


def branch_op(op: str) -> str:
    return {"<": "b.lt", "<=": "b.le", ">": "b.gt", ">=": "b.ge", "==": "b.eq", "!=": "b.ne"}[op]


def cond_op(op: str) -> str:
    return {"<": "lt", "<=": "le", ">": "gt", ">=": "ge", "==": "eq", "!=": "ne"}[op]


def compile_file(src: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    source = src.read_text(encoding="utf-8")
    tokens = lex(source)
    ast = Parser(tokens).parse()
    tac, symbols = TacEmitter().emit_program(ast)
    arm = ArmGenerator(tac).generate()
    opt_arm = peephole_opt(arm)

    (out_dir / "tokens.txt").write_text("\n".join(t.text() for t in tokens if t.kind != "EOF") + "\n", encoding="utf-8")
    (out_dir / "qast.json").write_text(json.dumps(ast.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "qtac.txt").write_text(tac, encoding="utf-8")
    (out_dir / "symbols.json").write_text(json.dumps(symbols, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "qsort.s").write_text(arm, encoding="utf-8")
    (out_dir / "qsort_opt.s").write_text(opt_arm, encoding="utf-8")


def peephole_opt(asm: str) -> str:
    lines = asm.splitlines()
    out: list[str] = []
    for line in lines:
        if re.fullmatch(r"\s*mov\s+(x\d+),\s*\1", line):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile QL source to tokens, QAST, QTAC, and ARM64 assembly.")
    parser.add_argument("source", nargs="?", default="qsort.ql", help="QL source file")
    parser.add_argument("-o", "--out-dir", default="build", help="output directory")
    args = parser.parse_args(list(argv) if argv is not None else None)
    compile_file(Path(args.source), Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
