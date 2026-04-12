#
# Imports
#

# Standard library
import json
import shutil
from pathlib import Path

# Third party
import pytest

# Paths
import dev.paths as paths

# Environment
from dotenv import load_dotenv
load_dotenv()

#
# Constants
#

# Save real paths at import time (before any swap)
REAL_FRONTEND_SRC = paths.FRONTEND_SRC
REAL_PROJECT_ROOT = paths.PROJECT_ROOT

#
# Helper Functions
#


def redirect_frontend_src(tmp_path: Path) -> Path:
    """Redirect FRONTEND_SRC to tmp_path/src"""
    src = tmp_path / "src"
    src.mkdir()
    paths.FRONTEND_SRC = src
    return src


def redirect_project_root(tmp_path: Path) -> Path:
    """Copy seed CSVs and global translations.json to tmp_path, swap PROJECT_ROOT + FRONTEND_SRC"""
    project = tmp_path / "project"

    # Copy seed CSVs
    for table in ["theme", "languages", "timezones"]:
        dest = project / "data" / "tables" / "meta" / table
        dest.mkdir(parents=True)
        shutil.copy2(
            REAL_PROJECT_ROOT / "data" / "tables" / "meta" / table / "seed.csv",
            dest / "seed.csv",
        )

    # Copy global translations.json
    translations_dest = (
        project / "frontend" / "src"
        / "providers" / "TranslationProvider"
    )
    translations_dest.mkdir(parents=True)
    shutil.copy2(
        REAL_FRONTEND_SRC / "providers" / "TranslationProvider" / "translations.json",
        translations_dest / "translations.json",
    )

    paths.PROJECT_ROOT = project
    paths.FRONTEND_SRC = project / "frontend" / "src"
    return project


def restore_paths():
    """Restore all paths to their real values"""
    paths.FRONTEND_SRC = REAL_FRONTEND_SRC
    paths.PROJECT_ROOT = REAL_PROJECT_ROOT


def get_test_issues(data: dict) -> list:
    """Extract issues related to our test folder"""
    return [i for i in data.get("issues", []) if "_test_translations" in str(i)]


def has_issue_type(issues: list, issue_type: str) -> bool:
    """Check if any issue has the given type"""
    return any(i.get("type") == issue_type for i in issues)


#
# Fixtures for generate_translations tests
#


@pytest.fixture
def folder_with_all_languages(tmp_path):
    """Component directory with translations.json containing all languages"""
    src = redirect_frontend_src(tmp_path)
    from dev.translations.generate_translations import TARGET_LANGUAGES

    component_dir = src / "_test_generate_translations"
    component_dir.mkdir(parents=True)

    # Create translations.json with en + all target languages
    data = {"en": {"hello": "Hello"}}
    for lang in TARGET_LANGUAGES:
        data[lang] = {"hello": f"Hello in {lang}"}

    (component_dir / "translations.json").write_text(json.dumps(data))

    yield str(component_dir)

    restore_paths()


@pytest.fixture
def folder_without_en_json(tmp_path):
    """Component directory with translations.json that has no English key"""
    src = redirect_frontend_src(tmp_path)

    component_dir = src / "_test_generate_translations"
    component_dir.mkdir(parents=True)

    # Create translations.json with only es (no en)
    (component_dir / "translations.json").write_text(json.dumps({"es": {"hello": "Hola"}}))

    yield str(component_dir)

    restore_paths()


@pytest.fixture
def folder_with_empty_en_json(tmp_path):
    """Component directory with translations.json that has empty English"""
    src = redirect_frontend_src(tmp_path)

    component_dir = src / "_test_generate_translations"
    component_dir.mkdir(parents=True)
    (component_dir / "translations.json").write_text(json.dumps({"en": {}}))

    yield str(component_dir)

    restore_paths()


@pytest.fixture
def folder_without_en_json_for_all(tmp_path):
    """Component directory with translations.json that has no English key, for use with all=True"""
    src = redirect_frontend_src(tmp_path)

    component_dir = src / "_test_generate_translations"
    component_dir.mkdir(parents=True)

    # Create translations.json with only es (no en)
    (component_dir / "translations.json").write_text(json.dumps({"es": {"hello": "Hola"}}))

    yield str(component_dir)

    restore_paths()


@pytest.fixture
def folder_with_en_json_only(tmp_path):
    """Component directory with translations.json containing only English (needs generation)"""
    src = redirect_frontend_src(tmp_path)

    component_dir = src / "_test_generate_translations"
    component_dir.mkdir(parents=True)
    (component_dir / "translations.json").write_text(
        json.dumps({"en": {"hello": "Hello", "goodbye": "Goodbye"}})
    )

    yield str(component_dir)

    restore_paths()


@pytest.fixture
def translations_file_not_dir(tmp_path):
    """A directory named 'translations.json' (not a file) to test is_file() check"""
    src = redirect_frontend_src(tmp_path)

    base = src / "_test_generate_translations"
    base.mkdir(parents=True)

    # Create a directory named translations.json (not a file)
    translations_dir = base / "translations.json"
    translations_dir.mkdir()

    yield str(base)

    restore_paths()


#
# Fixtures for validate_translations tests
#


@pytest.fixture
def test_base_dir(tmp_path):
    """Provide a redirected _test_translations base directory for inline test use"""
    src = redirect_frontend_src(tmp_path)

    yield src / "_test_translations"

    restore_paths()


@pytest.fixture
def missing_language_files(tmp_path):
    """translations.json with only English (missing all other languages)"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    yield test_dir

    restore_paths()


@pytest.fixture
def key_mismatch(tmp_path):
    """translations.json where es is missing a key and has an extra key"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text(json.dumps({
        "en": {"hello": "Hello", "goodbye": "Goodbye"},
        "es": {"hello": "Hola", "extra": "Extra"},
    }))

    yield test_dir

    restore_paths()


@pytest.fixture
def invalid_json(tmp_path):
    """translations.json with malformed JSON"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text('{"en": {"hello": "Hello"}')  # Missing closing brace

    yield test_dir

    restore_paths()


@pytest.fixture
def invalid_format(tmp_path):
    """translations.json where a language entry is not a dict (array instead)"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text(json.dumps({
        "en": {"hello": "Hello"},
        "es": ["hello", "hola"],
    }))

    yield test_dir

    restore_paths()


@pytest.fixture
def invalid_key_value(tmp_path):
    """translations.json with empty key and empty value"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text(json.dumps({
        "en": {"hello": "Hello", "": "Empty key", "empty_value": ""},
        "es": {"hello": "Hola", "": "Clave vacia", "empty_value": ""},
    }))

    yield test_dir

    restore_paths()


@pytest.fixture
def component_uses_translations_no_folder(tmp_path):
    """Component that imports useTranslation but has no translations.json"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)
    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('_test_translations');
    return <div>{t('hello')}</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def component_with_hardcoded_text(tmp_path):
    """Component with hardcoded text that should use translations"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)
    component = test_base / "_test_translations.tsx"
    component.write_text("""
export function TestComponent() {
    return (
        <div>
            <label>Page Name Required</label>
            <button>Submit Form</button>
            <input placeholder="Enter your name here" />
        </div>
    );
}
""")

    yield component

    restore_paths()


@pytest.fixture
def component_with_path_mismatch(tmp_path):
    """Component where useTranslation path doesn't match location"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    # Create translations.json so we don't get missing_translations error
    (test_base / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('wrong/path/here');
    return <div>{t('hello')}</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def component_with_missing_key(tmp_path):
    """Component uses translation key that doesn't exist in translations.json"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    (test_base / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('_test_translations');
    return <div>{t('hello')}{t('missing_key')}</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def component_with_duplicate_use_translation(tmp_path):
    """Component that calls useTranslation multiple times with same path"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    (test_base / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('_test_translations');
    const { t: t2 } = useTranslation('_test_translations');
    return <div>{t('hello')}</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def component_with_aliased_t(tmp_path):
    """Component that aliases the t function"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    (test_base / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t: tTest } = useTranslation('_test_translations');
    return <div>{tTest('hello')}</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def orphaned_translation_folder(tmp_path):
    """translations.json exists but component doesn't use translations"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    # Create translations.json with content
    (test_base / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    # Create component that does NOT use translations
    component = test_base / "_test_translations.tsx"
    component.write_text("""
export function TestComponent() {
    return <div>Static content</div>;
}
""")

    yield test_base

    restore_paths()


@pytest.fixture
def global_translations_extra_key(tmp_path):
    """Add an extra key to the English section of global translations.json"""
    project = redirect_project_root(tmp_path)

    # Modify the copied translations.json
    translations_file = (
        project / "frontend" / "src"
        / "providers" / "TranslationProvider" / "translations.json"
    )
    data = json.loads(translations_file.read_text(encoding="utf-8"))
    data["en"]["_test_extra_key_not_in_seed"] = "Test Value"
    translations_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    yield

    restore_paths()


@pytest.fixture
def global_translations_missing_key(tmp_path):
    """Remove a key from the English section of global translations.json"""
    project = redirect_project_root(tmp_path)

    # Modify the copied translations.json
    translations_file = (
        project / "frontend" / "src"
        / "providers" / "TranslationProvider" / "translations.json"
    )
    data = json.loads(translations_file.read_text(encoding="utf-8"))
    en_data = data.get("en", {})
    first_key = list(en_data.keys())[0]
    del en_data[first_key]
    data["en"] = en_data
    translations_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    yield first_key

    restore_paths()


@pytest.fixture
def global_translations_file_missing(tmp_path):
    """Delete the global translations.json from the copy"""
    project = redirect_project_root(tmp_path)

    # Delete from the copy
    translations_file = (
        project / "frontend" / "src"
        / "providers" / "TranslationProvider" / "translations.json"
    )
    translations_file.unlink()

    yield

    restore_paths()


@pytest.fixture
def seed_csv_file_missing(tmp_path):
    """Delete a seed CSV file from the copy"""
    project = redirect_project_root(tmp_path)

    # Delete from the copy
    seed_csv = project / "data" / "tables" / "meta" / "theme" / "seed.csv"
    seed_csv.unlink()

    yield

    restore_paths()


@pytest.fixture
def global_translations_invalid_json(tmp_path):
    """Corrupt the global translations.json copy with invalid JSON"""
    project = redirect_project_root(tmp_path)

    # Corrupt the copy
    translations_file = (
        project / "frontend" / "src"
        / "providers" / "TranslationProvider" / "translations.json"
    )
    translations_file.write_text('{"invalid": "json"', encoding="utf-8")

    yield

    restore_paths()


@pytest.fixture
def orphaned_translation_folder_no_component(tmp_path):
    """translations.json exists but there's no component file at all"""
    src = redirect_frontend_src(tmp_path)

    # Create a subdirectory with translations.json but no component
    orphan_dir = src / "_test_translations" / "orphan_subdir"
    orphan_dir.mkdir(parents=True)

    (orphan_dir / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    # No component file created
    yield orphan_dir

    restore_paths()


@pytest.fixture
def orphaned_translation_folder_nonstandard_name(tmp_path):
    """translations.json with component that has non-standard name"""
    src = redirect_frontend_src(tmp_path)

    # Create a subdirectory with translations.json and a non-standard component name
    orphan_dir = src / "_test_translations" / "nonstandard_subdir"
    orphan_dir.mkdir(parents=True)

    (orphan_dir / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    # Create component with non-standard name (not nonstandard_subdir.tsx, not index.tsx)
    component = orphan_dir / "Main.tsx"
    component.write_text("""
export function Main() {
    return <div>Static content</div>;
}
""")

    yield orphan_dir

    restore_paths()


@pytest.fixture
def orphaned_translation_folder_no_tsx_files(tmp_path):
    """translations.json with no .tsx or .ts files in directory (only other file types)"""
    src = redirect_frontend_src(tmp_path)

    # Create a subdirectory with translations.json but only non-component files
    orphan_dir = src / "_test_translations" / "no_tsx_subdir"
    orphan_dir.mkdir(parents=True)

    (orphan_dir / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    # Create non-component files only (no .tsx or .ts)
    (orphan_dir / "styles.css").write_text(".test { color: red; }")
    (orphan_dir / "README.md").write_text("# Test")

    yield orphan_dir

    restore_paths()


@pytest.fixture
def empty_translation_folder(tmp_path):
    """translations.json with empty object (no languages)"""
    src = redirect_frontend_src(tmp_path)

    test_dir = src / "_test_translations"
    test_dir.mkdir(parents=True)
    (test_dir / "translations.json").write_text(json.dumps({}))

    yield test_dir

    restore_paths()


@pytest.fixture
def component_with_whitespace_button(tmp_path):
    """Component with button containing only whitespace (filtered out)"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)
    component = test_base / "_test_translations.tsx"
    component.write_text("""
export function TestComponent() {
    return (
        <div>
            {/* Button with whitespace only - should be filtered */}
            <button>   </button>
            <a>   </a>
        </div>
    );
}
""")

    yield component

    restore_paths()


@pytest.fixture
def test_tsx_file(tmp_path):
    """A .test.tsx file that should be excluded from component discovery"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    # This file should be excluded due to .test.tsx pattern
    component = test_base / "SomeComponent.test.tsx"
    component.write_text("""
export function TestComponent() {
    return <div>Test File Content</div>;
}
""")

    yield component

    restore_paths()


@pytest.fixture
def translation_folder_missing_en_json(tmp_path):
    """translations.json with es but no en key (missing reference language)"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)

    # Create translations.json with only es (no en)
    (test_base / "translations.json").write_text(json.dumps({"es": {"hello": "Hola"}}))

    # Create component that uses translations
    component = test_base / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('_test_translations');
    return <div>{t('hello')}</div>;
}
""")

    yield test_base

    restore_paths()


@pytest.fixture
def component_with_filtered_text(tmp_path):
    """Component with text patterns that should be filtered out (not flagged)"""
    src = redirect_frontend_src(tmp_path)

    test_base = src / "_test_translations"
    test_base.mkdir(parents=True)
    component = test_base / "_test_translations.tsx"
    component.write_text("""
export function TestComponent() {
    return (
        <div>
            {/* Lowercase text - filtered (line 170) */}
            <label>lowercase text here</label>

            {/* JSX expression in text - filtered (line 172) */}
            <label>Hello {name} World</label>

            {/* Short text - filtered (line 174) */}
            <label>Hi</label>

            {/* All caps text - filtered (line 176) */}
            <label>LOADING...</label>

            {/* Variable-like placeholder - filtered (line 199) */}
            <input placeholder="$variable" />
            <input placeholder="@mention" />
            <input placeholder="callback()" />

            {/* Placeholder with JSX expression - filtered (line 195) */}
            <input placeholder="{dynamicText}" />

            {/* Placeholder all caps - filtered (line 197) */}
            <input placeholder="ENTER TEXT" />

            {/* Empty button - filtered (line 216) */}
            <button></button>

            {/* Button with lowercase - filtered (line 218) */}
            <button>click here</button>

            {/* Button with JSX expression - filtered (line 220) */}
            <button>Click {action} Now</button>

            {/* Link with short text - filtered (line 222) */}
            <a>Go</a>

            {/* Link all caps - filtered (line 224) */}
            <a>SUBMIT NOW</a>
        </div>
    );
}
""")

    yield component

    restore_paths()
