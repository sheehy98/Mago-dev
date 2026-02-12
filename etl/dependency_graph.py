#
# Imports
#

# Standard library
import logging
import re
from collections import deque
from typing import Callable, Optional

# Logging
logger = logging.getLogger(__name__)


#
# Helper Functions
#


def parse_foreign_keys(sql_content: str, table_name: Optional[str] = None) -> list[str]:
    """
    Extract referenced tables from REFERENCES clauses in SQL content

    Handles two syntax variants:
      - Unquoted schema: REFERENCES meta.lucide_icon ("ID")
      - Quoted schema:   REFERENCES "test00000000000000000000".help__theme ("ID")

    Self-references (where referenced table == table_name) are excluded.

    @param sql_content (str): SQL file content
    @param table_name (Optional[str]): Table name to exclude self-references
    @returns list[str] - Deduplicated list of schema.table dependency strings
    """

    # Match both quoted and unquoted schema.table patterns after REFERENCES
    pattern = re.compile(
        r'REFERENCES\s+'
        r'(?:"([^"]+)"\.(\w+)'       # Quoted schema: "schema".table
        r'|(\w+)\.(\w+))'            # Unquoted schema: schema.table
        r'\s*\(',                     # Opening paren for column list
        re.IGNORECASE,
    )

    seen: set[str] = set()
    result: list[str] = []

    for match in pattern.finditer(sql_content):
        # Extract schema and table from whichever group matched
        if match.group(1) is not None:
            ref_table = f"{match.group(1)}.{match.group(2)}"
        else:
            ref_table = f"{match.group(3)}.{match.group(4)}"

        # Skip self-references
        if table_name and ref_table == table_name:
            continue

        # Deduplicate
        if ref_table not in seen:
            seen.add(ref_table)
            result.append(ref_table)

    return result


def build_dependency_graph(
    sql_files: list[str],
    extract_fn: Callable[[str], Optional[str]],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """
    Build a dependency graph from create.sql files

    For each file, extracts the table name via extract_fn and parses FKs.

    @param sql_files (list[str]): Paths to create.sql files
    @param extract_fn (Callable): Function that takes a file path and returns schema.table or None
    @returns tuple - (graph: {table: set of dependency tables}, file_map: {table: file_path})
    """

    graph: dict[str, set[str]] = {}
    file_map: dict[str, str] = {}

    for sql_file in sql_files:
        # Extract table name
        name = extract_fn(sql_file)
        if name is None:
            continue

        # Read file and parse FKs
        try:
            with open(sql_file) as f:
                content = f.read()
        except Exception:
            continue

        deps = parse_foreign_keys(content, table_name=name)
        graph[name] = set(deps)
        file_map[name] = sql_file

    return graph, file_map


def topological_sort(graph: dict[str, set[str]]) -> list[str]:
    """
    Topological sort using Kahn's algorithm (BFS from zero-dependency nodes)

    Returns nodes in dependency order: leaves first, dependents after their
    dependencies. External dependencies (referenced but not in the graph) are
    silently ignored.

    @param graph (dict[str, set[str]]): {node: set of dependency nodes}
    @returns list[str] - Topologically ordered list of node names
    """

    if not graph:
        return []

    # Build in-degree map considering only edges within the graph
    in_degree: dict[str, int] = dict.fromkeys(graph, 0)
    for node in graph:
        for dep in graph[node]:
            if dep in graph:
                in_degree[node] += 1

    # Start with zero-dependency nodes
    queue: deque[str] = deque()
    for node, degree in in_degree.items():
        if degree == 0:
            queue.append(node)

    # BFS
    result: list[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)

        # Decrement in-degree for nodes that depend on this one
        for other, deps in graph.items():
            if node in deps and other in in_degree:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    # Check for cycles
    if len(result) != len(graph):
        missing = set(graph.keys()) - set(result)
        logger.warning(f"Cycle detected in dependency graph, unresolved nodes: {missing}")

    return result
