
from dataclasses import dataclass
from lexer import tokenize


# ---------------- AST NODE CLASSES ----------------

@dataclass
class Program:
    imports: list
    functions: list


@dataclass
class Function:
    name: str
    parameters: list
    body: list


@dataclass
class Return:
    expression: object


@dataclass
class Assignment:
    name: str
    expression: object


@dataclass
class BinaryOp:
    operator: str
    left: object
    right: object


@dataclass
class Number:
    value: int | float


@dataclass
class Variable:
    name: str


@dataclass
class Call:
    name: str
    arguments: list


@dataclass
class ExpressionStatement:
    expression: object


# ---------------- PARSER ----------------

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    def current(self):
        return self.tokens[self.position]

    def peek(self, offset=1):
        index = min(
            self.position + offset,
            len(self.tokens) - 1
        )
        return self.tokens[index]

    def advance(self):
        token = self.current()
        if token.type != "EOF":
            self.position += 1
        return token

    def expect(self, value):
        token = self.current()

        if token.value != value:
            raise SyntaxError(
                f"Expected {value!r} at line {token.line}, "
                f"column {token.column}; found {token.value!r}"
            )

        return self.advance()

    def expect_identifier(self):
        token = self.current()

        if token.type != "IDENTIFIER":
            raise SyntaxError(
                f"Expected identifier at line {token.line}, "
                f"column {token.column}"
            )

        return self.advance().value

    def parse(self):
        imports = []
        functions = []

        while self.current().type != "EOF":
            if self.current().value == "import":
                self.advance()
                imports.append(self.expect_identifier())

            elif self.current().value == "function":
                functions.append(self.parse_function())

            else:
                token = self.current()
                raise SyntaxError(
                    f"Unexpected token {token.value!r} "
                    f"at line {token.line}, column {token.column}"
                )

        return Program(imports, functions)

    def parse_function(self):
        self.expect("function")
        name = self.expect_identifier()

        self.expect("(")
        parameters = []

        if self.current().value != ")":
            while True:
                parameters.append(self.expect_identifier())

                if self.current().value != ",":
                    break

                self.advance()

        self.expect(")")
        self.expect("{")

        body = []

        while (
            self.current().value != "}"
            and self.current().type != "EOF"
        ):
            body.append(self.parse_statement())

        self.expect("}")

        return Function(name, parameters, body)

    def parse_statement(self):
        if self.current().value == "return":
            self.advance()

            if self.current().value == ";":
                self.advance()
                return Return(None)

            expression = self.parse_expression()
            self.expect(";")
            return Return(expression)

        # Assignment: result = calculate(10, 20);
        if (
            self.current().type == "IDENTIFIER"
            and self.peek().value == "="
        ):
            name = self.advance().value
            self.expect("=")
            expression = self.parse_expression()
            self.expect(";")
            return Assignment(name, expression)

        expression = self.parse_expression()
        self.expect(";")
        return ExpressionStatement(expression)

    # Addition and subtraction
    def parse_expression(self):
        node = self.parse_multiplicative()

        while self.current().value in ("+", "-"):
            operator = self.advance().value
            right = self.parse_multiplicative()
            node = BinaryOp(operator, node, right)

        return node

    # Multiplication and division
    def parse_multiplicative(self):
        node = self.parse_primary()

        while self.current().value in ("*", "/"):
            operator = self.advance().value
            right = self.parse_primary()
            node = BinaryOp(operator, node, right)

        return node

    def parse_primary(self):
        token = self.current()

        if token.value == "(":
            self.advance()
            node = self.parse_expression()
            self.expect(")")
            return node

        if token.type == "INTEGER":
            self.advance()
            return Number(int(token.value))

        if token.type == "FLOAT":
            self.advance()
            return Number(float(token.value))

        if token.type == "IDENTIFIER":
            name = self.advance().value

            # Function call: calculate(10, 20)
            if self.current().value == "(":
                self.advance()
                arguments = []

                if self.current().value != ")":
                    while True:
                        arguments.append(self.parse_expression())

                        if self.current().value != ",":
                            break

                        self.advance()

                self.expect(")")
                return Call(name, arguments)

            return Variable(name)

        raise SyntaxError(
            f"Unexpected token {token.value!r} "
            f"at line {token.line}, column {token.column}"
        )


# ---------------- AST PRINTER ----------------

def print_ast(node, indent=0):
    prefix = " " * indent

    if isinstance(node, Program):
        print(f"{prefix}Imports: {node.imports}")
        print(f"{prefix}Functions:")
        for function in node.functions:
            print_ast(function, indent + 2)

    elif isinstance(node, Function):
        print(f"{prefix}Function: {node.name}")
        print(f"{prefix}Parameters: {node.parameters}")
        print(f"{prefix}Body:")
        for statement in node.body:
            print_ast(statement, indent + 2)

    elif isinstance(node, Assignment):
        print(f"{prefix}Assignment: {node.name}")
        print_ast(node.expression, indent + 2)

    elif isinstance(node, Return):
        print(f"{prefix}Return")
        if node.expression is not None:
            print_ast(node.expression, indent + 2)

    elif isinstance(node, BinaryOp):
        print(f"{prefix}BinaryOp: {node.operator}")
        print_ast(node.left, indent + 2)
        print_ast(node.right, indent + 2)

    elif isinstance(node, Call):
        print(f"{prefix}Call: {node.name}")
        for argument in node.arguments:
            print_ast(argument, indent + 2)

    elif isinstance(node, Number):
        print(f"{prefix}Number: {node.value}")

    elif isinstance(node, Variable):
        print(f"{prefix}Variable: {node.name}")

    elif isinstance(node, ExpressionStatement):
        print(f"{prefix}ExpressionStatement")
        print_ast(node.expression, indent + 2)


# ---------------- TEST REAL SOURCE FILE ----------------

if __name__ == "__main__":
    filename = "examples/main.lang"

    with open(filename, "r", encoding="utf-8") as file:
        source = file.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()

    print("ABSTRACT SYNTAX TREE")
    print("====================")
    print_ast(ast)
