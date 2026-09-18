import os
import re
import hashlib
import json
import sys

# Cache file used to remember previous compilation
CACHE_FILE = ".compiler_cache.json"


# --------------------------------------------------
# 1. Calculate SHA-256 hash of a file
# --------------------------------------------------
def file_hash(filename):
    with open(filename, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --------------------------------------------------
# 2. Find imported modules in a .lang file
# --------------------------------------------------
def find_dependencies(filename):
    dependencies = []

    with open(filename, "r") as f:
        content = f.read()

    # Detect statements such as:
    # import math
    # import util

    matches = re.findall(
        r"\bimport\s+([A-Za-z_][A-Za-z0-9_]*)",
        content
    )

    for module in matches:
        dependencies.append(module + ".lang")

    return dependencies


# --------------------------------------------------
# 3. Load previous compilation information
# --------------------------------------------------
def load_cache():

    if os.path.exists(CACHE_FILE):

        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    return {}


# --------------------------------------------------
# 4. Save compilation information
# --------------------------------------------------
def save_cache(cache):

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


# --------------------------------------------------
# 5. Build dependency graph
# --------------------------------------------------
def build_dependency_graph(source_dir, files):

    graph = {}

    for filename in files:

        path = os.path.join(source_dir, filename)

        graph[filename] = find_dependencies(path)

    return graph


# --------------------------------------------------
# 6. Find all files affected by a changed file
# --------------------------------------------------
def find_affected_files(changed_file, graph):

    affected = set()

    def find_dependents(file):

        # Avoid processing the same file twice
        if file in affected:
            return

        affected.add(file)

        # Find files that depend on this file
        for module, dependencies in graph.items():

            if file in dependencies:
                find_dependents(module)

    find_dependents(changed_file)

    return affected


# --------------------------------------------------
# 7. Simple prototype compilation
# --------------------------------------------------
def compile_file(filename):

    print("  Compiling:", filename)

    with open(filename, "r") as f:
        source = f.read()

    # Simple lexical tokenization
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|\d+|[+\-*/=();{},]",
        source
    )

    print("    Tokens generated:", len(tokens))


# --------------------------------------------------
# 8. Main compiler
# --------------------------------------------------
def main():

    # Check command-line arguments
    if len(sys.argv) < 2:

        print("Usage:")
        print("  python compiler.py examples")
        return

    source_dir = sys.argv[1]

    # Check source directory
    if not os.path.isdir(source_dir):

        print("Directory not found:", source_dir)
        return

    # Find all .lang files
    files = [
        filename
        for filename in os.listdir(source_dir)
        if filename.endswith(".lang")
    ]

    files.sort()

    if not files:

        print("No .lang files found.")
        return

    print()
    print("========================================")
    print("     INCREMENTAL COMPILER - REVIEW 1")
    print("========================================")
    print()

    # --------------------------------------------------
    # Build dependency graph
    # --------------------------------------------------

    graph = build_dependency_graph(source_dir, files)

    print("Dependency Graph:")

    for filename in files:

        dependencies = graph[filename]

        if dependencies:

            print(
                f"  {filename} -> "
                f"{', '.join(dependencies)}"
            )

        else:

            print(f"  {filename} -> None")

    print()

    # --------------------------------------------------
    # Load previous cache
    # --------------------------------------------------

    cache = load_cache()

    # Calculate current hashes
    current_hashes = {}

    for filename in files:

        path = os.path.join(source_dir, filename)

        current_hashes[filename] = file_hash(path)

    # --------------------------------------------------
    # FIRST BUILD
    # --------------------------------------------------

    if not cache:

        print("No previous build found.")
        print("Performing FULL COMPILATION...")
        print()

        for filename in files:

            path = os.path.join(source_dir, filename)

            compile_file(path)

        # Save hashes for next compilation
        save_cache(current_hashes)

        print()
        print("----------------------------------------")
        print(
            f"Full compilation completed: "
            f"{len(files)}/{len(files)} files"
        )
        print("----------------------------------------")

        return

    # --------------------------------------------------
    # Detect changed files
    # --------------------------------------------------

    changed_files = set()

    for filename in files:

        old_hash = cache.get(filename)
        new_hash = current_hashes[filename]

        if old_hash != new_hash:

            changed_files.add(filename)

    # --------------------------------------------------
    # No changes
    # --------------------------------------------------

    if not changed_files:

        print("No source files changed.")
        print("Nothing needs to be recompiled.")

        return

    # --------------------------------------------------
    # Display changed files
    # --------------------------------------------------

    print("Changed files:")

    for filename in sorted(changed_files):

        print(" ", filename)

    print()

    # --------------------------------------------------
    # Find all affected files
    # --------------------------------------------------

    all_affected = set()

    for changed_file in changed_files:

        affected = find_affected_files(
            changed_file,
            graph
        )

        all_affected.update(affected)

    print("Files requiring recompilation:")

    for filename in sorted(all_affected):

        print(" ", filename)

    print()

    # --------------------------------------------------
    # Incremental compilation
    # --------------------------------------------------

    print("INCREMENTAL COMPILATION...")
    print()

    for filename in sorted(all_affected):

        path = os.path.join(source_dir, filename)

        compile_file(path)

    # --------------------------------------------------
    # Update cache
    # --------------------------------------------------

    save_cache(current_hashes)

    print()
    print("----------------------------------------")
    print(
        f"Incremental compilation completed: "
        f"{len(all_affected)}/{len(files)} files"
    )
    print("----------------------------------------")


# --------------------------------------------------
# Program starts here
# --------------------------------------------------
if __name__ == "__main__":
    main()