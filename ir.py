
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


class IRGenerator:
    def __init__(self):
        self.instructions = []
        self.temp_count = 0

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def generate_expression(self, node):
        if isinstance(node, Number):
            return str(node.value)

        if isinstance(node, Variable):
            return node.name

        if isinstance(node, BinaryOp):
            left = self.generate_expression(node.left)
            right = self.generate_expression(node.right)
            temp = self.new_temp()

            self.instructions.append(
                f"{temp} = {left} {node.operator} {right}"
            )
            return temp

        if isinstance(node, Call):
            arguments = [
                self.generate_expression(arg)
                for arg in node.arguments
            ]

            for argument in arguments:
                self.instructions.append(f"param {argument}")

            temp = self.new_temp()
            self.instructions.append(
                f"{temp} = call {node.name}, {len(arguments)}"
            )
            return temp

        raise TypeError(
            f"Unsupported expression: {type(node).__name__}"
        )

    def generate(self, program):
        self.instructions = []
        self.temp_count = 0

        for function in program.functions:
            self.instructions.append(f"{function.name}:")

            for statement in function.body:
                if isinstance(statement, Assignment):
                    value = self.generate_expression(
                        statement.expression
                    )
                    self.instructions.append(
                        f"{statement.name} = {value}"
                    )

                elif isinstance(statement, Return):
                    if statement.expression is None:
                        self.instructions.append("return")
                    else:
                        value = self.generate_expression(
                            statement.expression
                        )
                        self.instructions.append(
                            f"return {value}"
                        )

                elif isinstance(statement, ExpressionStatement):
                    self.generate_expression(
                        statement.expression
                    )

        return self.instructions


if __name__ == "__main__":
    with open(
        "examples/main.lang", "r", encoding="utf-8"
    ) as file:
        source = file.read()

    program = Parser(tokenize(source)).parse()
    generator = IRGenerator()
    instructions = generator.generate(program)

    print("THREE-ADDRESS INTERMEDIATE CODE")
    print("===============================")

    for instruction in instructions:
        print(instruction)
