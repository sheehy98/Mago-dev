#
# Imports
#

# Standard library
import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

# Third party
from deep_translator import GoogleTranslator

# Configure logging
logger = logging.getLogger(__name__)

#
# Constants
#

# All supported languages (excluding English, the source language)
TARGET_LANGUAGES = [
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

# Language code mapping for Google Translate (where our codes differ from Google's)
LANGUAGE_CODE_MAP = {
    "zh": "zh-CN",
    "he": "iw",
    "no": "no",
}


#
# Helper Functions
#


def translate_values(en_data: dict[str, str], target_lang: str) -> dict[str, str]:
    """
    Translate all values from English to the target language

    @param en_data (dict): English key-value pairs
    @param target_lang (str): Target language code
    @returns dict - Translated key-value pairs with same keys
    """

    # Map our language code to Google Translate's code if needed
    google_lang = LANGUAGE_CODE_MAP.get(target_lang, target_lang)

    # Create translator instance
    translator = GoogleTranslator(source="en", target=google_lang)

    return {key: translator.translate(value) for key, value in en_data.items()}


def load_translations_file(file_path: Path) -> dict[str, dict[str, str]] | None:
    """
    Load and parse a translations.json file

    @param file_path (Path): Path to translations.json
    @returns dict | None - Nested dict keyed by language code, or None if invalid
    """

    if not file_path.exists():
        return None

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return None

    return data


def save_translations_file(file_path: Path, data: dict[str, dict[str, str]]) -> None:
    """
    Write a translations.json file with sorted keys

    @param file_path (Path): Path to translations.json
    @param data (dict): Nested dict keyed by language code
    """

    # Sort languages, and sort keys within each language
    sorted_data = {}
    for lang in sorted(data.keys()):
        sorted_data[lang] = dict(sorted(data[lang].items()))

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def generate_translations_for_folder(folder_path: str, force: bool = False) -> int:
    """
    Generate missing translations for a single component's translations.json

    Reads the English translations, translates to all missing languages, and updates the file.
    Skips languages that already exist and are complete unless force=True.

    @param folder_path (str): Path to the component directory containing translations.json
    @param force (bool): If True, regenerate even if language exists
    @returns int - Number of languages updated
    """

    file_path = Path(folder_path) / "translations.json"

    # Load existing translations
    data = load_translations_file(file_path)
    if data is None:
        logger.warning(f"No translations.json found in {folder_path}, skipping")
        return 0

    # Get English translations
    en_data = data.get("en")
    if not en_data:
        logger.warning(f"No 'en' key in {folder_path}/translations.json, skipping")
        return 0

    en_keys = set(en_data.keys())
    languages_updated = 0

    for lang in TARGET_LANGUAGES:
        existing = data.get(lang)

        if existing and not force:
            existing_keys = set(existing.keys())
            missing_keys = en_keys - existing_keys
            extra_keys = existing_keys - en_keys

            # Nothing to do if keys are already in sync
            if not missing_keys and not extra_keys:
                continue

            # Translate missing keys and merge with existing
            if missing_keys:
                logger.info(f"  Adding {len(missing_keys)} missing key(s) to {lang}...")
                missing_data = {k: en_data[k] for k in missing_keys}
                translated_missing = translate_values(missing_data, lang)
                existing.update(translated_missing)
                time.sleep(0.2)

            # Remove extra keys not present in English
            if extra_keys:
                logger.info(f"  Removing {len(extra_keys)} extra key(s) from {lang}...")
                for key in extra_keys:
                    del existing[key]

            data[lang] = existing
            languages_updated += 1
            continue

        # Language doesn't exist or force=True — translate everything
        logger.info(f"  Translating to {lang}...")
        data[lang] = translate_values(en_data, lang)
        languages_updated += 1

        # Small delay to avoid rate limiting
        time.sleep(0.2)

    # Write updated file
    if languages_updated > 0:
        save_translations_file(file_path, data)

    return languages_updated


def find_incomplete_folders(src_root: str) -> list[str]:
    """
    Find all component directories with incomplete translations.json files

    A file is incomplete if any target language is missing or has mismatched keys.

    @param src_root (str): Root path to scan (e.g., frontend/src)
    @returns list[str] - List of component directory paths that need translation generation
    """

    incomplete = []
    root = Path(src_root)

    for translations_file in root.rglob("translations.json"):
        if not translations_file.is_file():
            continue

        # Load the file
        data = load_translations_file(translations_file)
        if data is None:
            continue

        # Get English keys
        en_data = data.get("en")
        if not en_data:
            continue

        en_keys = set(en_data.keys())

        # Check if any target language is missing or has mismatched keys
        for lang in TARGET_LANGUAGES:
            lang_data = data.get(lang)

            # Missing language
            if lang_data is None:
                incomplete.append(str(translations_file.parent))
                break

            # Language exists but keys don't match
            if set(lang_data.keys()) != en_keys:
                incomplete.append(str(translations_file.parent))
                break

    return sorted(incomplete)


#
# Handler Functions
#


def generate_translations(
    path: Optional[str] = None, force: bool = False, generate_all: bool = False
) -> dict[str, Any]:
    """
    Generate missing translations in translations.json files

    Translates English keys to all target languages using Google Translate.
    Supports generating for a single component or scanning all incomplete files.

    @param path (Optional[str]): Path to a specific component directory
    @param force (bool): If True, regenerate even if language exists
    @param generate_all (bool): If True, scan and generate for all incomplete files
    @returns dict[str, Any] - Response with generation results
    """

    logger.info("generate_translations called")

    # Validate: require either path or all, but not both
    if not path and not generate_all:
        return {
            "status": "error",
            "message": "Must provide either 'path' or 'all' parameter",
            "folders_processed": 0,
            "files_generated": 0,
            "details": [],
        }

    if path and generate_all:
        return {
            "status": "error",
            "message": "Cannot provide both 'path' and 'all' parameters",
            "folders_processed": 0,
            "files_generated": 0,
            "details": [],
        }

    # Single path mode
    if path:
        logger.info(f"Generating translations for: {path}")
        count = generate_translations_for_folder(path, force=force)

        return {
            "status": "success",
            "message": f"Generated {count} translations for {path}",
            "folders_processed": 1,
            "files_generated": count,
            "details": [{"folder": path, "files_generated": count}],
        }

    # All incomplete folders mode
    from dev.paths import FRONTEND_SRC
    src_root = FRONTEND_SRC

    logger.info(f"Scanning for incomplete translations in {src_root}...")
    folders = find_incomplete_folders(str(src_root))

    # All files are complete
    if not folders:
        return {
            "status": "success",
            "message": "All translation files are complete",
            "folders_processed": 0,
            "files_generated": 0,
            "details": [],
        }

    # Process each incomplete folder
    total_generated = 0
    details = []

    for folder_path in folders:
        logger.info(f"Processing: {folder_path}")
        count = generate_translations_for_folder(folder_path, force=force)
        total_generated += count
        details.append({"folder": folder_path, "files_generated": count})

    logger.info(
        f"Done! Updated {total_generated} languages across {len(folders)} files"
    )

    return {
        "status": "success",
        "message": f"Updated {total_generated} languages across {len(folders)} files",
        "folders_processed": len(folders),
        "files_generated": total_generated,
        "details": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate translation files")
    parser.add_argument("-s", "--staging", action="store_true", help="Use staging environment")
    parser.add_argument("--path", help="Path to a specific component directory")
    parser.add_argument("--force", action="store_true", help="Regenerate even if language exists")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="generate_all",
        help="Generate for all incomplete files",
    )
    args = parser.parse_args()
    result = generate_translations(
        path=args.path, force=args.force, generate_all=args.generate_all
    )
    print(json.dumps(result, indent=2))
