
import os
import sys
import json
import hashlib
from dataclasses import fields, is_dataclass
from collections import defaultdict, deque

from lexer import tokenize
from parser import Parser
from semantic import SemanticAnalyzer
from ir import IRGenerator


CACHE_FILE = ".compiler_cache.json"
CACHE_VERSION = 2


# --------------------------------------------------
# 1. Read and parse source files
# --------------------------------------------------

def read_source(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def parse_source(source):
    tokens = tokenize(source)
    return Parser(tokens).parse()


# --------------------------------------------------
# 2. Convert AST into stable data and hash it
# --------------------------------------------------

def ast_to_data(node):
    if is_dataclass(node):
        return {
            "node": type(node).__name__,
            **{
                field.name: ast_to_data(getattr(node, field.name))
                for field in fields(node)
            }
        }

    if isinstance(node, list):
        return [ast_to_data(item) for item in node]

    if isinstance(node, dict):
        return {
            key: ast_to_data(value)
            for key, value in sorted(node.items())
        }

    return node


def hash_ast(program):
    serialized = json.dumps(
        ast_to_data(program),
        sort_keys=True,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


# --------------------------------------------------
# 3. Build dependency graph
# --------------------------------------------------

def build_dependency_graph(programs):
    return {
        module: set(program.imports)
        for module, program in programs.items()
    }


def build_reverse_graph(graph):
    reverse = defaultdict(set)

    for module, dependencies in graph.items():
        for dependency in dependencies:
            reverse[dependency].add(module)

    return reverse


def find_affected(changed, reverse_graph):
    affected = set(changed)
    queue = deque(changed)

    while queue:
        current = queue.popleft()

        for dependent in reverse_graph.get(current, set()):
            if dependent not in affected:
                affected.add(dependent)
                queue.append(dependent)

    return affected


# --------------------------------------------------
# 4. Dependency-safe compilation order
# --------------------------------------------------

def topological_order(units, graph):
    units = set(units)
    visited = set()
    visiting = set()
    order = []

    def visit(module):
        if module in visiting:
            raise ValueError(
                f"Circular dependency detected at '{module}'"
            )

        if module in visited:
            return

        visiting.add(module)

        for dependency in sorted(graph.get(module, set())):
            if dependency in units:
                visit(dependency)

        visiting.remove(module)
        visited.add(module)
        order.append(module)

    for module in sorted(units):
        visit(module)

    return order


# --------------------------------------------------
# 5. Persistent cache
# --------------------------------------------------

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        print("Warning: Cache is unreadable; rebuilding.")
        return {}


def save_cache(cache):
    temporary_file = CACHE_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=4)

    os.replace(temporary_file, CACHE_FILE)


# --------------------------------------------------
# 6. Display dependency graph
# --------------------------------------------------

def show_graph(graph):
    print("\nDependency Graph:")

    for module in sorted(graph):
        dependencies = sorted(graph[module])

        if dependencies:
            print(
                f"  {module}.lang -> "
                + ", ".join(
                    dependency + ".lang"
                    for dependency in dependencies
                )
            )
        else:
            print(f"  {module}.lang -> None")


# --------------------------------------------------
# 7. Main compiler
# --------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python compiler.py examples")
        return

    source_dir = sys.argv[1]

    if not os.path.isdir(source_dir):
        print("Directory not found:", source_dir)
        return

    paths = sorted(
        filename
        for filename in os.listdir(source_dir)
        if filename.endswith(".lang")
    )

    if not paths:
        print("No .lang files found.")
        return

    print("\n========================================")
    print(" INCREMENTAL COMPILER - REVIEW 2")
    print("========================================")

    programs = {}

    # Lexical analysis and parsing
    try:
        for filename in paths:
            module = filename[:-5]
            path = os.path.join(source_dir, filename)
            source = read_source(path)

            programs[module] = parse_source(source)

        print("\n[lex/parse] All source files parsed successfully.")

    except (SyntaxError, OSError) as error:
        print("\nCompilation failed:", error)
        return

    graph = build_dependency_graph(programs)
    show_graph(graph)

    # Check imported modules
    missing = []

    for module, dependencies in graph.items():
        for dependency in sorted(dependencies):
            if dependency not in programs:
                missing.append(
                    f"{module}.lang imports missing module "
                    f"'{dependency}'"
                )

    if missing:
        print("\nDependency errors:")
        for message in missing:
            print("  ", message)
        return

    # Semantic analysis across all modules
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(programs)

    if errors:
        print("\nSemantic errors:")
        for error in errors:
            print("  ", error)

        print("\nBuild stopped because semantic analysis failed.")
        return

    print("[sema] No semantic errors found.")

    # Calculate AST hashes
    current_hashes = {
        module: hash_ast(program)
        for module, program in programs.items()
    }

    previous = load_cache()

    cache_is_valid = (
        previous.get("version") == CACHE_VERSION
        and isinstance(previous.get("units"), dict)
    )

    old_units = (
        previous.get("units", {})
        if cache_is_valid
        else {}
    )

    # Detect changed and added modules
    changed = {
        module
        for module, digest in current_hashes.items()
        if (
            not cache_is_valid
            or module not in old_units
            or old_units[module].get("hash") != digest
        )
    }

    # Detect deleted modules
    removed = set(old_units) - set(programs)

    reverse_graph = build_reverse_graph(graph)

    old_graph = {
        module: set(entry.get("dependencies", []))
        for module, entry in old_units.items()
    }

    old_reverse_graph = build_reverse_graph(old_graph)

    affected = find_affected(changed, reverse_graph)
    affected |= find_affected(removed, old_reverse_graph)

    # Do not compile deleted modules
    affected.intersection_update(programs)

    # Detect cycles and establish compilation order
    try:
        topological_order(programs, graph)
        order = topological_order(affected, graph)

    except ValueError as error:
        print("\nDependency error:", error)
        return

    # --------------------------------------------------
    # 8. Handle no recompilation and clean deleted cache
    # --------------------------------------------------

    if not affected:
        cleaned_units = {
            module: entry
            for module, entry in old_units.items()
            if (
                module in programs
                and entry.get("hash") == current_hashes.get(module)
            )
        }

        new_cache = {
            "version": CACHE_VERSION,
            "units": cleaned_units,
        }

        try:
            save_cache(new_cache)

        except OSError as error:
            print("\nWarning: Could not save cache:", error)
            return

        print("\n[hash] No AST changes detected.")

        if removed:
            print(
                "[cache] Deleted modules removed: "
                + ", ".join(sorted(removed))
            )
        else:
            print("[cache] All modules are up to date.")

        print("Nothing needs to be recompiled.")
        return

    print("\nChanged modules:")

    for module in sorted(changed):
        print("  ", module + ".lang")

    if removed:
        print("\nDeleted modules:")
        for module in sorted(removed):
            print("  ", module + ".lang")

    print("\nModules requiring recompilation:")

    for module in order:
        print("  ", module + ".lang")

    print("\nCompilation order:")
    print("  " + " -> ".join(order))

    # --------------------------------------------------
    # 9. Generate IR for affected modules
    # --------------------------------------------------

    new_units = {}

    for module in order:
        print(f"\n[codegen] Generating IR for {module}.lang")

        generator = IRGenerator()
        instructions = generator.generate(programs[module])

        new_units[module] = {
            "hash": current_hashes[module],
            "dependencies": sorted(graph[module]),
            "ir": instructions,
        }

        for instruction in instructions:
            print("   ", instruction)

    # --------------------------------------------------
    # 10. Reuse valid cache entries for unchanged modules
    # --------------------------------------------------

    for module in programs:
        if module in new_units:
            continue

        if (
            module in old_units
            and old_units[module].get("hash") == current_hashes[module]
            and "ir" in old_units[module]
        ):
            new_units[module] = {
                "hash": current_hashes[module],
                "dependencies": sorted(graph[module]),
                "ir": old_units[module]["ir"],
            }

        else:
            # Generate IR if a valid cache entry is unavailable
            generator = IRGenerator()
            instructions = generator.generate(programs[module])

            new_units[module] = {
                "hash": current_hashes[module],
                "dependencies": sorted(graph[module]),
                "ir": instructions,
            }

    # Save only modules that still exist
    new_cache = {
        "version": CACHE_VERSION,
        "units": {
            module: new_units[module]
            for module in programs
        },
    }

    try:
        save_cache(new_cache)

    except OSError as error:
        print("\nWarning: Could not save cache:", error)
        return

    print("\n[cache] Intermediate code cache saved.")

    if removed:
        print(
            "[cache] Deleted modules removed: "
            + ", ".join(sorted(removed))
        )

    print(
        f"[build] Recompiled {len(affected)} "
        f"of {len(programs)} modules."
    )

    print("[build] Compilation completed successfully.")


if __name__ == "__main__":
    main()
