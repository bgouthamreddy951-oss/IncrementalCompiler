
class IRRuntime:
    def __init__(self, module_units, programs=None):
        self.instructions = []
        self.labels = {}
        self.module_units = module_units
        self.programs = programs or {}

        # Link IR from all modules.
        for module, unit in module_units.items():
            self.instructions.extend(unit["ir"])

        # Build the function label table.
        for index, instruction in enumerate(self.instructions):
            label = instruction.strip()
            if label.endswith(":"):
                self.labels[label[:-1]] = index

        # Collect function parameter names from parsed programs.
        self.parameters = {}
        for program in self.programs.values():
            for function in program.functions:
                self.parameters[function.name] = function.parameters

    def value_of(self, operand, environment):
        operand = operand.strip()

        if operand in environment:
            return environment[operand]

        try:
            return int(operand)
        except ValueError:
            pass

        try:
            return float(operand)
        except ValueError:
            pass

        raise RuntimeError(
            f"Undefined variable or invalid value: {operand}"
        )

    def execute_function(self, name, arguments=None):
        if arguments is None:
            arguments = []

        # Built-in print function.
        if name == "print":
            if len(arguments) != 1:
                raise RuntimeError(
                    "print() expects exactly one argument"
                )
            print(arguments[0])
            return None

        if name not in self.labels:
            raise RuntimeError(
                f"Function '{name}' was not found during linking"
            )

        parameter_names = self.parameters.get(name, [])

        if len(arguments) != len(parameter_names):
            raise RuntimeError(
                f"Function '{name}' expects "
                f"{len(parameter_names)} argument(s), "
                f"but received {len(arguments)}"
            )

        # Bind arguments to function parameters.
        environment = dict(zip(parameter_names, arguments))
        pending = []
        pc = self.labels[name] + 1

        while pc < len(self.instructions):
            instruction = self.instructions[pc].strip()

            # Stop at the next function label.
            if instruction.endswith(":"):
                break

            if instruction.startswith("param "):
                operand = instruction[len("param "):]
                pending.append(
                    self.value_of(operand, environment)
                )

            elif " = call " in instruction:
                target, call_info = instruction.split(
                    " = call ", 1
                )
                function_name, count_text = call_info.rsplit(",", 1)
                function_name = function_name.strip()
                count = int(count_text.strip())

                if len(pending) < count:
                    raise RuntimeError(
                        f"Insufficient parameters for call to "
                        f"'{function_name}'"
                    )

                call_arguments = pending[-count:] if count else []

                if count:
                    del pending[-count:]

                result = self.execute_function(
                    function_name,
                    call_arguments
                )
                environment[target.strip()] = result

            elif instruction == "return":
                return None

            elif instruction.startswith("return "):
                operand = instruction[len("return "):]
                return self.value_of(operand, environment)

            elif " = " in instruction:
                target, expression = instruction.split(" = ", 1)

                matched = False

                for operator in (" + ", " - ", " * ", " / "):
                    if operator in expression:
                        left_text, right_text = expression.split(
                            operator, 1
                        )
                        left = self.value_of(
                            left_text, environment
                        )
                        right = self.value_of(
                            right_text, environment
                        )

                        if operator == " + ":
                            result = left + right
                        elif operator == " - ":
                            result = left - right
                        elif operator == " * ":
                            result = left * right
                        else:
                            if right == 0:
                                raise RuntimeError("Division by zero")
                            result = left / right

                        environment[target.strip()] = result
                        matched = True
                        break

                if not matched:
                    environment[target.strip()] = self.value_of(
                        expression, environment
                    )

            else:
                raise RuntimeError(
                    f"Unsupported IR instruction: {instruction}"
                )

            pc += 1

        return None

    def run(self, entry_function="main"):
        if entry_function not in self.labels:
            raise RuntimeError(
                f"Entry function '{entry_function}' was not found"
            )

        self.execute_function(entry_function)
