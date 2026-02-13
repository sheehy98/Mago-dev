#
# Imports
#

# Standard library
import argparse
import csv
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#

# Supported language codes (matching all languages in database)
SUPPORTED_LANGUAGES = [
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "ru",
    "ja",
    "zh",
    "ko",
    "ar",
    "hi",
    "nl",
    "sv",
    "no",
    "da",
    "fi",
    "pl",
    "tr",
    "el",
    "ga",
    "he",
    "eo",
    "vi",
]


def find_translation_folders(root_path: str) -> list[str]:
    """
    Recursively find all translations/ folders in the src directory

    @param root_path (str): Root path to search (should be frontend/src)
    @returns List[str] - List of paths to translations folders
    """

    translation_folders = []
    root = Path(root_path)

    # Walk through the directory tree
    for path in root.rglob("translations"):
        if path.is_dir():
            translation_folders.append(str(path))

    return translation_folders


def find_component_files(root_path: str) -> list[str]:
    """
    Recursively find all React/TypeScript component files in the src directory

    Finds all .tsx and .ts files, excluding:
    - Test files (*.test.tsx, *.test.ts, *.spec.tsx, *.spec.ts)
    - Type definition files (types.ts, *.d.ts)
    - Utility files in utils/ directories
    - Provider files in providers/ directories (they don't use translations)

    @param root_path (str): Root path to search (should be frontend/src)
    @returns List[str] - List of paths to component files
    """

    component_files = []
    root = Path(root_path)

    # Patterns to exclude
    exclude_patterns = [
        r"\.test\.(tsx?|ts)$",
        r"\.spec\.(tsx?|ts)$",
        r"types\.ts$",
        r"\.d\.ts$",
    ]

    # Walk through the directory tree
    for path in root.rglob("*.tsx"):
        # Skip if matches exclude patterns
        if any(re.search(pattern, str(path)) for pattern in exclude_patterns):
            continue
        component_files.append(str(path))

    for path in root.rglob("*.ts"):
        # Skip if matches exclude patterns
        if any(re.search(pattern, str(path)) for pattern in exclude_patterns):
            continue
        # Skip utils and providers directories (they're not components)
        if "utils" in path.parts or "providers" in path.parts:
            continue
        component_files.append(str(path))

    return sorted(component_files)


def extract_translation_keys(file_path: str) -> set[str]:
    """
    Extract all translation keys used in a component file

    Finds all t('...') and t("...") calls using regex

    @param file_path (str): Path to the component file
    @returns Set[str] - Set of translation keys found
    """

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Pattern to match t('key') or t("key"), including aliased forms like tActions('key')
    # Matches: t('...'), t("..."), tActions('...'), tBookmarks('...'), etc.
    # Use word boundary (\b) to ensure we match t( but not .split( or .createElement(
    pattern = r"\bt(?:[A-Z]\w*)?\(['\"]([^'\"]+)['\"]\)"

    # Find all matches
    matches = re.findall(pattern, content)

    return set(matches)


def extract_hardcoded_text(file_path: str) -> list[dict[str, Any]]:
    """
    Extract hardcoded text strings from JSX that should be translated

    Finds hardcoded strings in:
    - JSX text nodes: >Text Content<
    - Common attributes: placeholder="...", title="...", label="...", aria-label="..."
    - Button/link text: <button>Text</button>, <a>Text</a>

    Filters out:
    - Single words or very short strings (< 3 characters)
    - All uppercase strings (likely constants)
    - Strings that are clearly code (variable names, etc.)

    @param file_path (str): Path to the component file
    @returns List[Dict[str, Any]] - List of hardcoded text with context
    """

    hardcoded_texts = []

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()
        content = "".join(lines)

    # Pattern 1: JSX text nodes - text between > and </ (closing tags)
    jsx_text_pattern = r">\s*([^\<]{1,}?)\s*</"
    for match in re.finditer(jsx_text_pattern, content):
        text = match.group(1).strip()
        if not text:
            continue
        if not text[0].isupper():
            continue
        if "{" in text or "}" in text:
            continue
        if len(text) < 3:
            continue
        if text.isupper() and len(text) > 5:
            continue
        line_num = content[: match.start()].count("\n") + 1
        hardcoded_texts.append(
            {
                "text": text,
                "type": "jsx_text_node",
                "line": line_num,
                "context": lines[line_num - 1].strip() if line_num <= len(lines) else "",
            }
        )

    # Pattern 2: Common attributes with hardcoded strings
    attribute_pattern = r'(placeholder|title|label|aria-label)=["\']([^"\']{3,})["\']'
    for match in re.finditer(attribute_pattern, content):
        attr_name = match.group(1)
        text = match.group(2).strip()
        if "{" in text or "}" in text:
            continue
        if text.isupper() and len(text) > 5:
            continue
        if text.startswith("$") or text.startswith("@") or "()" in text:
            continue
        line_num = content[: match.start()].count("\n") + 1
        hardcoded_texts.append(
            {
                "text": text,
                "type": f"attribute_{attr_name}",
                "line": line_num,
                "context": lines[line_num - 1].strip() if line_num <= len(lines) else "",
            }
        )

    # Pattern 3: Button/link text content
    button_pattern = r"<(button|a)[^>]*>([^\<]{1,}?)</(button|a)>"
    for match in re.finditer(button_pattern, content):
        tag_name = match.group(1)
        text = match.group(2).strip()
        if not text:
            continue
        if not text[0].isupper():
            continue
        if "{" in text or "}" in text:
            continue
        if len(text) < 3:
            continue
        if text.isupper() and len(text) > 5:
            continue
        line_num = content[: match.start()].count("\n") + 1
        hardcoded_texts.append(
            {
                "text": text,
                "type": f"{tag_name}_text",
                "line": line_num,
                "context": lines[line_num - 1].strip() if line_num <= len(lines) else "",
            }
        )

    return hardcoded_texts


def get_component_translation_path(component_file_path: str, src_root: str) -> str:
    """
    Map a component file path to its expected translation folder path

    Component: actions/LoadoutsAction/LoadoutsAction.tsx
    Translation folder: actions/LoadoutsAction/translations

    @param component_file_path (str): Full path to component file
    @param src_root (str): Root path to src directory
    @returns str - Expected translation folder path relative to src_root
    """

    component_path = Path(component_file_path)
    src_path = Path(src_root)
    relative_path = component_path.relative_to(src_path)
    component_folder = relative_path.parent
    translation_folder = component_folder / "translations"

    return str(translation_folder)


def get_expected_translation_path_from_component(component_file_path: str, src_root: str) -> str:
    """
    Get the expected translation path based on component location

    Component: frontend/src/templates/Recipes/Recipes.tsx
    Expected path: templates/Recipes

    @param component_file_path (str): Full path to component file
    @param src_root (str): Root path to src directory
    @returns str - Expected translation path (without /translations suffix)
    """

    component_path = Path(component_file_path)
    src_path = Path(src_root)
    relative_path = component_path.relative_to(src_path)
    component_folder = relative_path.parent

    return str(component_folder).replace("\\", "/")


def component_uses_translations(file_path: str) -> bool:
    """
    Check if a component uses translations

    Checks if component:
    1. Imports useTranslation
    2. Calls t('...') anywhere in the file

    @param file_path (str): Path to the component file
    @returns bool - True if component uses translations
    """

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Check if useTranslation is imported
    has_import = "useTranslation" in content

    # Check if t('...') or aliased t functions (tActions, tBookmarks, etc.) are called
    # Use word boundary to avoid false positives from split('/') or createElement('span')
    has_translation_call = bool(re.search(r"\bt(?:[A-Z]\w*)?\(['\"][^'\"]+['\"]\)", content))

    return has_import or has_translation_call


def validate_component_translations(
    component_file_path: str, src_root: str
) -> list[dict[str, Any]]:
    """
    Validate translation usage for a single component

    Checks:
    1. If component uses translations, translation folder should exist
    2. useTranslation() path matches component location
    3. All translation keys used in component exist in translation file
    4. Component should not have hardcoded text if it uses translations

    @param component_file_path (str): Path to component file
    @param src_root (str): Root path to src directory
    @returns List[Dict[str, Any]] - List of validation issues
    """

    issues = []

    # Check if component uses translations
    uses_translations = component_uses_translations(component_file_path)

    # Get expected translation folder path
    translation_folder_path = get_component_translation_path(component_file_path, src_root)
    full_translation_path = Path(src_root) / translation_folder_path

    # Extract translation keys used in component
    used_keys = extract_translation_keys(component_file_path)

    # Extract hardcoded text
    hardcoded_texts = extract_hardcoded_text(component_file_path)

    # If component uses translations, check that translation folder exists
    if uses_translations:
        # Check if useTranslation path matches component location
        # Extract ALL useTranslation calls (components may have multiple)
        expected_path = get_expected_translation_path_from_component(component_file_path, src_root)

        # Get all useTranslation paths from the component
        with open(component_file_path, encoding="utf-8") as f:
            content = f.read()

        # Pattern to match useTranslation('path') or useTranslation("path")
        pattern = r"\buseTranslation\(['\"]([^'\"]+)['\"]\)"
        use_translation_paths = re.findall(pattern, content)

        # Validate each useTranslation call
        for use_translation_path in use_translation_paths:
            if expected_path:
                # Normalize paths for comparison (handle both forward and backslashes)
                normalized_use_path = use_translation_path.replace("\\", "/")
                normalized_expected = expected_path.replace("\\", "/")

                # Check if paths match
                if normalized_use_path != normalized_expected:
                    issues.append(
                        {
                            "type": "translation_path_mismatch",
                            "component": component_file_path,
                            "use_translation_path": use_translation_path,
                            "expected_path": expected_path,
                            "message": f"useTranslation path '{use_translation_path}' does not match component location '{expected_path}'. Expected: '{expected_path}' based on file location.",
                        }
                    )

        # Check for duplicate useTranslation calls with the same path
        path_counts = Counter(use_translation_paths)
        for path, count in path_counts.items():
            if count > 1:
                issues.append(
                    {
                        "type": "duplicate_use_translation",
                        "component": component_file_path,
                        "path": path,
                        "count": count,
                        "message": f"useTranslation('{path}') is called {count} times in the same component. Use a single call instead.",
                    }
                )

        # Check for aliased t functions (e.g., { t: tActions })
        alias_pattern = r"\{\s*t\s*:\s*(t[A-Z]\w*)\s*\}"
        aliases = re.findall(alias_pattern, content)
        for alias in aliases:
            issues.append(
                {
                    "type": "aliased_translation_function",
                    "component": component_file_path,
                    "alias": alias,
                    "message": f"Translation function aliased as '{alias}'. Use 't' directly instead of creating aliases.",
                }
            )
        if not full_translation_path.exists():
            issues.append(
                {
                    "type": "component_missing_translations",
                    "component": component_file_path,
                    "message": f"Component uses translations but translation folder does not exist: {translation_folder_path}",
                }
            )
        else:
            # Load translation file (en.json) to check keys
            en_file = full_translation_path / "en.json"
            if en_file.exists():
                with open(en_file, encoding="utf-8") as f:
                    translation_data = json.load(f)

                # Check if all used keys exist in translation file
                translation_keys = set(translation_data.keys())
                missing_keys = used_keys - translation_keys

                for key in missing_keys:
                    issues.append(
                        {
                            "type": "component_missing_key",
                            "component": component_file_path,
                            "key": key,
                            "message": f"Translation key '{key}' used in component but not found in translation file",
                        }
                    )

        # Check for hardcoded text (should use translations instead)
        for hardcoded in hardcoded_texts:
            issues.append(
                {
                    "type": "component_hardcoded_text",
                    "component": component_file_path,
                    "text": hardcoded["text"],
                    "line": hardcoded["line"],
                    "context": hardcoded["context"],
                    "message": f"Hardcoded text found at line {hardcoded['line']}: '{hardcoded['text']}' (should use translation)",
                }
            )

    # If component doesn't use translations but has hardcoded text, flag it
    elif len(hardcoded_texts) > 0:
        issues.append(
            {
                "type": "component_needs_translations",
                "component": component_file_path,
                "hardcoded_count": len(hardcoded_texts),
                "message": f"Component has {len(hardcoded_texts)} hardcoded text strings but does not use translations",
            }
        )

    return issues


def validate_translation_folder(folder_path: str) -> list[dict[str, Any]]:
    """
    Validate a single translations folder

    Checks that:
    1. All 8 language files exist
    2. All files have the same exact set of keys
    3. Keys are non-empty strings
    4. Values are non-empty strings

    @param folder_path (str): Path to the translations folder
    @returns List[Dict[str, Any]] - List of validation issues (empty if valid)
    """

    issues = []
    folder = Path(folder_path)

    # Get all JSON files in the folder
    json_files = list(folder.glob("*.json"))

    # If no translation files exist, skip this folder (not an error)
    if len(json_files) == 0:
        return issues

    # Check that all required language files exist
    found_languages = set()
    translation_data: dict[str, dict[str, str]] = {}

    for lang in SUPPORTED_LANGUAGES:
        lang_file = folder / f"{lang}.json"

        if not lang_file.exists():
            issues.append(
                {
                    "type": "missing_file",
                    "folder": folder_path,
                    "language": lang,
                    "message": f"Missing translation file: {lang}.json in {folder_path}",
                }
            )
        else:
            found_languages.add(lang)

            # Try to load and parse the JSON file
            try:
                with open(lang_file, encoding="utf-8") as f:
                    data = json.load(f)

                    # Validate that it's a dictionary
                    if not isinstance(data, dict):
                        issues.append(
                            {
                                "type": "invalid_format",
                                "folder": folder_path,
                                "language": lang,
                                "message": f"Translation file {lang}.json is not a valid JSON object",
                            }
                        )
                        continue

                    # Validate keys and values
                    for key, value in data.items():
                        if not isinstance(key, str) or len(key) == 0:
                            issues.append(
                                {
                                    "type": "invalid_key",
                                    "folder": folder_path,
                                    "language": lang,
                                    "key": key,
                                    "message": f"Invalid key in {lang}.json: keys must be non-empty strings",
                                }
                            )

                        if not isinstance(value, str) or len(value) == 0:
                            issues.append(
                                {
                                    "type": "invalid_value",
                                    "folder": folder_path,
                                    "language": lang,
                                    "key": key,
                                    "message": f"Invalid value in {lang}.json for key '{key}': values must be non-empty strings",
                                }
                            )

                    translation_data[lang] = data

            except json.JSONDecodeError as e:
                issues.append(
                    {
                        "type": "json_parse_error",
                        "folder": folder_path,
                        "language": lang,
                        "message": f"Failed to parse {lang}.json: {str(e)}",
                    }
                )

    # If we have at least one translation file, check that all files have the same keys
    if len(found_languages) > 0 and len(translation_data) > 0:
        # Get the set of keys from the first language file
        reference_lang = list(translation_data.keys())[0]
        reference_keys = set(translation_data[reference_lang].keys())

        # Check each language file against the reference
        for lang, data in translation_data.items():
            lang_keys = set(data.keys())

            # Check for missing keys
            missing_keys = reference_keys - lang_keys
            for key in missing_keys:
                issues.append(
                    {
                        "type": "missing_key",
                        "folder": folder_path,
                        "language": lang,
                        "key": key,
                        "message": f"Missing key '{key}' in {lang}.json (present in {reference_lang}.json)",
                    }
                )

            # Check for extra keys
            extra_keys = lang_keys - reference_keys
            for key in extra_keys:
                issues.append(
                    {
                        "type": "extra_key",
                        "folder": folder_path,
                        "language": lang,
                        "key": key,
                        "message": f"Extra key '{key}' in {lang}.json (not present in {reference_lang}.json)",
                    }
                )

    return issues


def find_component_for_translation_folder(
    translation_folder_path: str, src_root: str
) -> str | None:
    """
    Find the component file that corresponds to a translation folder

    Translation folder: actions/LoadoutsAction/translations
    Component: actions/LoadoutsAction/LoadoutsAction.tsx (or any .tsx/.ts file in that folder)

    @param translation_folder_path (str): Path to translation folder relative to src_root
    @param src_root (str): Root path to src directory
    @returns str | None - Path to component file if found, None otherwise
    """

    translation_path = Path(src_root) / translation_folder_path
    component_folder = translation_path.parent

    # Look for component files in the parent folder
    # Try common patterns: ComponentName.tsx, index.tsx, or any .tsx/.ts file
    possible_names = [
        component_folder.name + ".tsx",
        component_folder.name + ".ts",
        "index.tsx",
        "index.ts",
    ]

    # First try exact matches
    for name in possible_names:
        component_file = component_folder / name
        if component_file.exists():
            return str(component_file)

    # If no exact match, find any .tsx or .ts file in the folder (excluding test files)
    for ext in ["*.tsx", "*.ts"]:
        for component_file in component_folder.glob(ext):
            # Skip test files (check filename only, not full path)
            filename = component_file.name.lower()
            if "test" not in filename and "spec" not in filename:
                return str(component_file)

    return None


def validate_orphaned_translation_folders(
    translation_folders: list[str], component_files: list[str], src_root: str
) -> list[dict[str, Any]]:
    """
    Check for translation folders that exist but aren't used by any component

    @param translation_folders (List[str]): List of translation folder paths (full paths)
    @param component_files (List[str]): List of component file paths (full paths)
    @param src_root (str): Root path to src directory
    @returns List[Dict[str, Any]] - List of validation issues
    """

    issues = []
    src_path = Path(src_root)

    # Create a set of translation folder paths (as full paths) that are used by components
    translation_folders_in_use = set()
    for component_file in component_files:
        if component_uses_translations(component_file):
            # Get the expected translation folder for this component (relative path)
            translation_folder_path = get_component_translation_path(component_file, src_root)
            if translation_folder_path:
                # Convert to full path for comparison
                full_translation_path = src_path / translation_folder_path
                normalized = str(full_translation_path.resolve()).replace("\\", "/")
                translation_folders_in_use.add(normalized)

    # Check each translation folder
    for folder_path in translation_folders:
        # Skip the global TranslationProvider translations folder (not tied to a component)
        if "providers/TranslationProvider/translations" in folder_path.replace("\\", "/"):
            continue

        # Normalize folder path for comparison
        normalized_folder = str(Path(folder_path).resolve()).replace("\\", "/")

        # Skip if this folder is used by a component
        if normalized_folder in translation_folders_in_use:
            continue

        # Check if translation folder has non-empty en.json
        en_file = Path(folder_path) / "en.json"
        if en_file.exists():
            with open(en_file, encoding="utf-8") as f:
                translation_data = json.load(f)

            # Only report if the file has actual translations (not empty)
            if translation_data and len(translation_data) > 0:
                # Find the corresponding component
                relative_folder_path = str(Path(folder_path).relative_to(src_path))
                component_file = find_component_for_translation_folder(
                    relative_folder_path, src_root
                )

                issues.append(
                    {
                        "type": "orphaned_translation_folder",
                        "folder": folder_path,
                        "component": component_file,
                        "key_count": len(translation_data),
                        "message": f"Translation folder has {len(translation_data)} keys but component does not use translations"
                        + (
                            f" (component: {component_file})"
                            if component_file
                            else " (no component found)"
                        ),
                    }
                )

    return issues


def validate_global_translations(project_root: str) -> list[dict[str, Any]]:
    """
    Validate that global translation keys match database seed CSV Name values

    Checks that the global translations en.json contains exactly the set of
    unique Name values from theme, languages, and timezones seed CSVs.

    @param project_root (str): Path to the project root directory
    @returns List[Dict[str, Any]] - List of validation issues
    """

    issues = []
    root = Path(project_root)

    # Seed CSV paths and their Name column
    seed_files = {
        "theme": root / "data" / "tables" / "meta" / "theme" / "seed.csv",
        "languages": root / "data" / "tables" / "meta" / "languages" / "seed.csv",
        "timezones": root / "data" / "tables" / "meta" / "timezones" / "seed.csv",
    }

    # Collect all unique Name values from seed CSVs
    expected_keys: set[str] = set()

    for table_name, seed_path in seed_files.items():
        if not seed_path.exists():
            issues.append(
                {
                    "type": "global_translations_seed_not_found",
                    "seed_file": str(seed_path),
                    "message": f"Seed CSV not found for {table_name}: {seed_path}",
                }
            )
            continue

        with open(seed_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                if name:
                    expected_keys.add(name)

    # Read the global translations en.json
    en_json_path = (
        root
        / "frontend"
        / "src"
        / "providers"
        / "TranslationProvider"
        / "translations"
        / "en.json"
    )

    if not en_json_path.exists():
        issues.append(
            {
                "type": "global_translations_missing",
                "file": str(en_json_path),
                "message": f"Global translations en.json not found: {en_json_path}",
            }
        )
        return issues

    try:
        with open(en_json_path, encoding="utf-8") as f:
            translation_data = json.load(f)
    except Exception as e:
        issues.append(
            {
                "type": "global_translations_missing",
                "file": str(en_json_path),
                "message": f"Failed to read global translations en.json: {e}",
            }
        )
        return issues

    # Compare keys
    actual_keys = set(translation_data.keys())

    # Check for missing keys (in seed CSVs but not in en.json)
    missing_keys = expected_keys - actual_keys
    for key in sorted(missing_keys):
        issues.append(
            {
                "type": "global_translations_missing_key",
                "key": key,
                "message": f"Key '{key}' found in seed CSV but missing from global translations en.json",
            }
        )

    # Check for extra keys (in en.json but not in seed CSVs)
    extra_keys = actual_keys - expected_keys
    for key in sorted(extra_keys):
        issues.append(
            {
                "type": "global_translations_extra_key",
                "key": key,
                "message": f"Key '{key}' in global translations en.json but not found in any seed CSV",
            }
        )

    return issues


#
# Handler Functions
#


def validate_translations() -> dict[str, Any]:
    """
    Validate translation files and component usage

    This function scans the frontend src directory for translations folders
    and validates that:
    1. All required language files exist (en, es, fr, de, it, pt, zh, ja)
    2. All translation files have the same exact set of keys
    3. Keys and values are valid (non-empty strings)
    4. All rendered text in components is covered by translation files
    5. Components with hardcoded text have translation files
    6. Translation keys used in code actually exist in translation files

    @returns Dict[str, Any] - Response with validation results
    """

    logger.info("validate_translations called")

    # Get paths from centralized module
    from dev.paths import FRONTEND_SRC, PROJECT_ROOT
    src_path = FRONTEND_SRC
    project_root = PROJECT_ROOT

    # Find all translation folders
    translation_folders = find_translation_folders(str(src_path))

    logger.info(f"Found {len(translation_folders)} translation folders")

    # Validate each translation folder
    translation_file_issues = []
    for folder_path in translation_folders:
        folder_issues = validate_translation_folder(folder_path)
        translation_file_issues.extend(folder_issues)

    # Find all component files
    component_files = find_component_files(str(src_path))

    logger.info(f"Found {len(component_files)} component files")

    # Validate each component
    component_issues = []
    for component_file in component_files:
        component_file_issues = validate_component_translations(component_file, str(src_path))
        component_issues.extend(component_file_issues)

    # Check for orphaned translation folders (folders with translations but no component using them)
    orphaned_issues = validate_orphaned_translation_folders(
        translation_folders, component_files, str(src_path)
    )
    component_issues.extend(orphaned_issues)

    # Validate global translations (database value names)
    global_issues = validate_global_translations(str(project_root))

    # Combine all issues
    all_issues = translation_file_issues + component_issues + global_issues

    # Categorize issues
    component_issue_types = [
        "component_missing_translations",
        "component_missing_key",
        "component_hardcoded_text",
        "component_needs_translations",
        "translation_path_mismatch",
        "orphaned_translation_folder",
        "duplicate_use_translation",
        "aliased_translation_function",
        "global_translations_missing",
        "global_translations_missing_key",
        "global_translations_extra_key",
        "global_translations_seed_not_found",
    ]

    # Separate component issues from translation file issues
    component_issues_filtered = [
        issue for issue in component_issues if issue.get("type") in component_issue_types
    ]
    translation_file_issues_filtered = [
        issue for issue in translation_file_issues if issue.get("type") not in component_issue_types
    ]

    # Build response
    is_valid = len(all_issues) == 0

    logger.info(
        f"validate_translations completed: {len(all_issues)} issues found "
        f"({len(component_issues_filtered)} component issues, "
        f"{len(translation_file_issues_filtered)} translation file issues) "
        f"in {len(translation_folders)} folders and {len(component_files)} components"
    )

    return {
        "status": "success" if is_valid else "validation_errors",
        "valid": is_valid,
        "message": "All translations are valid"
        if is_valid
        else f"Found {len(all_issues)} validation issues",
        "issues": all_issues,
        "total_issues": len(all_issues),
        "folders_checked": len(translation_folders),
        "components_checked": len(component_files),
        "component_issues": component_issues_filtered,
        "translation_file_issues": translation_file_issues_filtered,
        "component_issues_count": len(component_issues_filtered),
        "translation_file_issues_count": len(translation_file_issues_filtered),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate translation files")
    parser.parse_args()
    result = validate_translations()
    print(json.dumps(result, indent=2))
