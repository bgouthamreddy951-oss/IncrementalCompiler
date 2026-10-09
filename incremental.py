
import ast
import hashlib
import json
import os
from collections import defaultdict, deque


CACHE_FILE = ".incremental_cache.json"


# 1. Generate a stable SHA-256 hash from an AST
def ast_hash(source):
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise SyntaxError(
            f"Cannot hash invalid source: {error}"
        ) from error

    normalized_ast = ast.dump(
        tree,
        annotate_fields=True,
        include_attributes=False
    )

    return hashlib.sha256(
        normalized_ast.encode("utf-8")
    ).hexdigest()


# 2. Find imports and function calls in a source file
def extract_dependencies(source):
    tree = ast.parse(source)
    dependencies = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                dependencies.add(item.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                dependencies.add(node.module)

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                dependencies.add(node.func.id)

    return dependencies


# 3. Load persistent build cache
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


# 4. Save persistent build cache
def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=4)


# 5. Build reverse dependency relationships
def build_reverse_graph(dependencies):
    reverse_graph = defaultdict(set)

    for unit, deps in dependencies.items():
        for dependency in deps:
            reverse_graph[dependency].add(unit)

    return reverse_graph


# 6. Find changed units and all their dependents
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


# 7. Topologically order dependencies before dependents
def topological_order(units, dependencies):
    units = set(units)
    visited = set()
    visiting = set()
    result = []

    def visit(unit):
        if unit in visiting:
            raise ValueError(
                f"Circular dependency detected at '{unit}'"
            )

        if unit in visited:
            return

        visiting.add(unit)

        for dependency in dependencies.get(unit, set()):
            if dependency in units:
                visit(dependency)

        visiting.remove(unit)
        visited.add(unit)
        result.append(unit)

    for unit in sorted(units):
        visit(unit)

    return result


# 8. Decide what needs recompilation
def plan_incremental_build(source_units, old_hashes, dependencies):
    new_hashes = {
        unit: ast_hash(source)
        for unit, source in source_units.items()
    }

    changed = {
        unit
        for unit, digest in new_hashes.items()
        if old_hashes.get(unit) != digest
    }

    # Removed units must also invalidate their dependents.
    removed = set(old_hashes) - set(new_hashes)

    reverse_graph = build_reverse_graph(dependencies)
    affected = find_affected(changed | removed, reverse_graph)

    # Do not attempt to compile deleted units.
    affected.intersection_update(source_units)

    order = topological_order(affected, dependencies)

    return new_hashes, changed, affected, order


# 9. Demonstration
if __name__ == "__main__":
    units = {
        "math": """
def add(a, b):
    return a + b + 4
""",
        "util": """
from math import add

def calculate(x, y):
    return add(x, y)
""",
        "main": """
from util import calculate

def run():
    return calculate(2, 3)
""",
    }

    dependencies = {
        "math": set(),
        "util": {"math"},
        "main": {"util"},
    }

    old_cache = load_cache()

    old_hashes = {
        unit: entry["hash"]
        for unit, entry in old_cache.items()
        if isinstance(entry, dict) and "hash" in entry
    }

    new_hashes, changed, affected, order = (
        plan_incremental_build(
            units, old_hashes, dependencies
        )
    )

    print("INCREMENTAL BUILD PLAN")
    print("======================")
    print("Changed units:", sorted(changed))
    print("Affected units:", sorted(affected))
    print("Compilation order:", order)

    # This demo persists hashes only; IR caching will be added later.
    save_cache({
        unit: {"hash": digest}
        for unit, digest in new_hashes.items()
    })

    print("Hash cache saved.")
