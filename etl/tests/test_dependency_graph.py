#
# Imports
#

# Standard library
import os
import tempfile

# Dev module
from dev.etl.dependency_graph import (
    build_dependency_graph,
    parse_foreign_keys,
    topological_sort,
)


#
# Tests for parse_foreign_keys
#


def test_parse_foreign_keys_no_fks():
    """
    Story: SQL with no REFERENCES returns empty list

    Given SQL content with no foreign key references
    When I parse foreign keys
    Then an empty list is returned
    """

    # Act
    result = parse_foreign_keys('CREATE TABLE meta.users ("ID" SERIAL PRIMARY KEY);')

    # Assert
    assert result == []


def test_parse_foreign_keys_single_unquoted_schema():
    """
    Story: Single FK with unquoted schema is parsed

    Given SQL with a REFERENCES clause using unquoted schema
    When I parse foreign keys
    Then the referenced table is returned
    """

    # Arrange
    sql = """
    CREATE TABLE meta.widgets (
        "Avatar ID" INTEGER,
        FOREIGN KEY ("Avatar ID") REFERENCES meta.lucide_icon ("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["meta.lucide_icon"]


def test_parse_foreign_keys_single_quoted_schema():
    """
    Story: Single FK with quoted schema is parsed

    Given SQL with a REFERENCES clause using quoted schema
    When I parse foreign keys
    Then the referenced table is returned without quotes
    """

    # Arrange
    sql = """
    CREATE TABLE "test00000000000000000000".help__settings (
        "Theme ID" INTEGER,
        FOREIGN KEY ("Theme ID") REFERENCES "test00000000000000000000".help__theme ("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["test00000000000000000000.help__theme"]


def test_parse_foreign_keys_multiple_different_tables():
    """
    Story: Multiple FKs to different tables are all returned

    Given SQL with REFERENCES to multiple different tables
    When I parse foreign keys
    Then all referenced tables are returned
    """

    # Arrange
    sql = """
    CREATE TABLE meta.group__member (
        "Group ID" INTEGER,
        "User ID" INTEGER,
        FOREIGN KEY ("Group ID") REFERENCES meta.group ("ID"),
        FOREIGN KEY ("User ID") REFERENCES meta.user ("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["meta.group", "meta.user"]


def test_parse_foreign_keys_self_reference_excluded():
    """
    Story: Self-references are excluded from results

    Given SQL where a table references itself
    When I parse foreign keys with the table_name parameter
    Then the self-reference is excluded
    """

    # Arrange
    sql = """
    CREATE TABLE meta.recipes__units (
        "ID" SERIAL,
        "Base Unit ID" INTEGER,
        FOREIGN KEY ("Base Unit ID") REFERENCES meta.recipes__units ("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql, table_name="meta.recipes__units")

    # Assert
    assert result == []


def test_parse_foreign_keys_on_delete_cascade():
    """
    Story: ON DELETE CASCADE doesn't break parsing

    Given SQL with REFERENCES followed by ON DELETE CASCADE
    When I parse foreign keys
    Then the referenced table is correctly extracted
    """

    # Arrange
    sql = """
    CREATE TABLE "test".steps__ingredients (
        "Step ID" INTEGER,
        FOREIGN KEY ("Step ID") REFERENCES "test".pages__recipes__steps ("ID") ON DELETE CASCADE
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["test.pages__recipes__steps"]


def test_parse_foreign_keys_no_space_before_paren():
    """
    Story: FK without space before column paren is parsed

    Given SQL where REFERENCES has no space before the opening paren
    When I parse foreign keys
    Then the referenced table is correctly extracted
    """

    # Arrange
    sql = """
    CREATE TABLE meta.pages (
        "Avatar ID" INTEGER,
        FOREIGN KEY ("Avatar ID") REFERENCES meta.lucide_icon("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["meta.lucide_icon"]


def test_parse_foreign_keys_deduplicated():
    """
    Story: Duplicate references are deduplicated

    Given SQL with multiple REFERENCES to the same table
    When I parse foreign keys
    Then the table appears only once
    """

    # Arrange
    sql = """
    CREATE TABLE meta.recipes__ingredients (
        "Weight Unit ID" INTEGER,
        "Volume Unit ID" INTEGER,
        FOREIGN KEY ("Weight Unit ID") REFERENCES meta.recipes__units ("ID"),
        FOREIGN KEY ("Volume Unit ID") REFERENCES meta.recipes__units ("ID")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["meta.recipes__units"]


def test_parse_foreign_keys_composite_columns():
    """
    Story: Composite FK columns are handled correctly

    Given SQL with a composite FOREIGN KEY referencing multiple columns
    When I parse foreign keys
    Then the referenced table is correctly extracted
    """

    # Arrange
    sql = """
    CREATE TABLE "test".steps__containers (
        "Container ID" INTEGER,
        "Key" TEXT,
        FOREIGN KEY ("Container ID", "Key") REFERENCES "test".pages__recipes__containers ("ID", "Key")
    );
    """

    # Act
    result = parse_foreign_keys(sql)

    # Assert
    assert result == ["test.pages__recipes__containers"]


#
# Tests for build_dependency_graph
#


def test_build_dependency_graph_empty_list():
    """
    Story: Empty file list produces empty graph

    Given an empty list of SQL files
    When I build the dependency graph
    Then both graph and file_map are empty
    """

    # Act
    graph, file_map = build_dependency_graph([], lambda f: None)

    # Assert
    assert graph == {}
    assert file_map == {}


def test_build_dependency_graph_no_fks():
    """
    Story: Files with no FKs produce nodes with empty dependency sets

    Given SQL files that have no REFERENCES clauses
    When I build the dependency graph
    Then each table appears as a node with empty dependencies
    """

    # Arrange — create temp SQL files with name mapping
    files = []
    name_map = {}
    for table_name, content in [
        ("meta.table_a", 'CREATE TABLE meta.table_a ("ID" SERIAL);'),
        ("meta.table_b", 'CREATE TABLE meta.table_b ("ID" SERIAL);'),
    ]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(content)
            files.append(f.name)
            name_map[f.name] = table_name

    try:
        # Act
        graph, _file_map = build_dependency_graph(files, lambda p: name_map.get(p))

        # Assert
        assert "meta.table_a" in graph
        assert "meta.table_b" in graph
        assert graph["meta.table_a"] == set()
        assert graph["meta.table_b"] == set()
    finally:
        for path in files:
            os.unlink(path)


def test_build_dependency_graph_linear_chain():
    """
    Story: Linear dependency chain A -> B -> C is captured

    Given three SQL files where C depends on B, B depends on A
    When I build the dependency graph
    Then the dependencies are correctly represented
    """

    # Arrange
    sqls = {
        "meta.a": 'CREATE TABLE meta.a ("ID" SERIAL);',
        "meta.b": 'CREATE TABLE meta.b ("ID" SERIAL, FOREIGN KEY ("AID") REFERENCES meta.a ("ID"));',
        "meta.c": 'CREATE TABLE meta.c ("ID" SERIAL, FOREIGN KEY ("BID") REFERENCES meta.b ("ID"));',
    }

    files = []
    name_map = {}
    for name, content in sqls.items():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(content)
            files.append(f.name)
            name_map[f.name] = name

    try:
        # Act
        graph, _file_map = build_dependency_graph(files, lambda p: name_map.get(p))

        # Assert
        assert graph["meta.a"] == set()
        assert graph["meta.b"] == {"meta.a"}
        assert graph["meta.c"] == {"meta.b"}
    finally:
        for path in files:
            os.unlink(path)


def test_build_dependency_graph_real_files():
    """
    Story: Real create.sql files produce a valid graph

    Given actual create.sql files from data/tables/meta/
    When I build the dependency graph
    Then the graph contains real table nodes
    """

    # Arrange
    from dev.etl.create_tables import find_create_sql_files
    from dev.etl.seed_tables import extract_table_name_from_create_sql

    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    sql_files = find_create_sql_files(tables_dir, usernames=["meta"])

    # Act
    graph, _file_map = build_dependency_graph(sql_files, extract_table_name_from_create_sql)

    # Assert — graph should have nodes
    assert len(graph) > 0

    # All values should be sets
    for deps in graph.values():
        assert isinstance(deps, set)

    # meta.lucide_icon should have no dependencies (it's a leaf)
    if "meta.lucide_icon" in graph:
        assert graph["meta.lucide_icon"] == set()


#
# Tests for topological_sort
#


def test_topological_sort_empty_graph():
    """
    Story: Empty graph produces empty list

    Given an empty dependency graph
    When I topologically sort it
    Then an empty list is returned
    """

    # Act
    result = topological_sort({})

    # Assert
    assert result == []


def test_topological_sort_no_dependencies():
    """
    Story: All independent nodes are returned

    Given a graph where no node has dependencies
    When I topologically sort it
    Then all nodes are returned
    """

    # Arrange
    graph = {"a": set(), "b": set(), "c": set()}

    # Act
    result = topological_sort(graph)

    # Assert
    assert set(result) == {"a", "b", "c"}


def test_topological_sort_linear_chain():
    """
    Story: Linear chain is sorted in correct order

    Given a chain c -> b -> a (c depends on b, b depends on a)
    When I topologically sort it
    Then a comes before b, and b comes before c
    """

    # Arrange
    graph = {"a": set(), "b": {"a"}, "c": {"b"}}

    # Act
    result = topological_sort(graph)

    # Assert
    assert result.index("a") < result.index("b")
    assert result.index("b") < result.index("c")


def test_topological_sort_diamond():
    """
    Story: Diamond dependency shape is sorted correctly

    Given a diamond: d depends on b and c, both depend on a
    When I topologically sort it
    Then a comes before b and c, which come before d
    """

    # Arrange
    graph = {"a": set(), "b": {"a"}, "c": {"a"}, "d": {"b", "c"}}

    # Act
    result = topological_sort(graph)

    # Assert
    assert result.index("a") < result.index("b")
    assert result.index("a") < result.index("c")
    assert result.index("b") < result.index("d")
    assert result.index("c") < result.index("d")


def test_topological_sort_cycle():
    """
    Story: Cyclic graph returns partial result and logs warning

    Given a graph with a cycle (a -> b -> a)
    When I topologically sort it
    Then the cycle nodes are excluded from the result
    """

    # Arrange — a and b form a cycle, c is independent
    graph = {"a": {"b"}, "b": {"a"}, "c": set()}

    # Act
    result = topological_sort(graph)

    # Assert — only the non-cyclic node is resolved
    assert "c" in result
    assert len(result) < len(graph)


def test_build_dependency_graph_unreadable_file():
    """
    Story: Unreadable file is skipped during graph building

    Given a file path that cannot be read
    When I build the dependency graph
    Then the unreadable file is skipped and others are processed
    """

    # Arrange — one valid temp file, one path that doesn't exist
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write('CREATE TABLE meta.good ("ID" SERIAL);')
        good_file = f.name

    bad_file = "/nonexistent/path/create.sql"

    def extract(path):
        if path == good_file:
            return "meta.good"
        return "meta.bad"

    try:
        # Act
        graph, file_map = build_dependency_graph([good_file, bad_file], extract)

        # Assert — good file is in graph, bad file is skipped
        assert "meta.good" in graph
        assert "meta.bad" not in graph
        assert good_file in file_map.values()
    finally:
        os.unlink(good_file)
