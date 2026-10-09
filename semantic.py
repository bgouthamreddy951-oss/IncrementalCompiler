
from pathlib import Path

from lexer import tokenize
from parser import (
    Parser,
    Program,
    Function,
    Return,
    Assignment,
    BinaryOp,
    Number,
    Variable,
    Call,
    ExpressionStatement,
)


class SemanticAnalyzer:
    def __init__(self):
        self.errors = []
        self.functions = {}
        self.scopes = {}
        self.return_types = {}

    def error(self, message):
        self.errors.append(message)

    def analyze(self, programs):
        # Register every function before checking function calls.
        for module, program in programs.items():
            for function in program.functions:
                if function.name in self.functions:
                    self.error(
                        f"Duplicate function '{function.name}' "
                        f"in module '{module}'"
                    )
                else:
                    self.functions[function.name] = function

        # Analyze each function body.
        for module, program in programs.items():
            for function in program.functions:
                self.analyze_function(module, function)

        return self.errors

    def analyze_function(self, module, function):
        scope = set(function.parameters)
        self.scopes[(module, function.name)] = scope

        for statement in function.body:
            self.check_statement(
                module, function, statement, scope
            )

    def check_statement(self, module, function, node, scope):
        if isinstance(node, Assignment):
            self.check_expression(module, function, node.expression, scope)
            scope.add(node.name)

        elif isinstance(node, Return):
            if node.expression is not None:
                self.check_expression(
                    module, function, node.expression, scope
                )

        elif isinstance(node, ExpressionStatement):
            self.check_expression(
                module, function, node.expression, scope
            )

    def check_expression(self, module, function, node, scope):
        if isinstance(node, (Number,)):
            return

        if isinstance(node, Variable):
            if node.name not in scope:
                self.error(
                    f"Undeclared variable '{node.name}' "
                    f"in function '{function.name}' "
                    f"({module}.lang)"
                )
            return

        if isinstance(node, BinaryOp):
            self.check_expression(module, function, node.left, scope)
            self.check_expression(module, function, node.right, scope)
            return

        if isinstance(node, Call):
            if node.name not in self.functions:
                # print() is a built-in function.
                if node.name != "print":
                    self.error(
                        f"Unknown function '{node.name}' "
                        f"in {module}.lang"
                    )
            else:
                target = self.functions[node.name]

                if len(node.arguments) != len(target.parameters):
                    self.error(
                        f"Function '{node.name}' expects "
                        f"{len(target.parameters)} argument(s), "
                        f"got {len(node.arguments)}"
                    )

            for argument in node.arguments:
                self.check_expression(
                    module, function, argument, scope
                )


def load_programs():
    programs = {}

    for path in sorted(Path("examples").glob("*.lang")):
        source = path.read_text(encoding="utf-8")
        tokens = tokenize(source)
        programs[path.stem] = Parser(tokens).parse()

    return programs


if __name__ == "__main__":
    programs = load_programs()
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(programs)

    print("SEMANTIC ANALYSIS — ALL MODULES")
    print("================================")

    for module, program in programs.items():
        print(f"{module}.lang: {len(program.functions)} function(s)")

    if errors:
        print("\nSemantic errors:")
        for error in errors:
            print("-", error)
    else:
        print("\nSemantic analysis passed.")
        print("No semantic errors found.")
