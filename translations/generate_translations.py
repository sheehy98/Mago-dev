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


def generate_translations_for_folder(folder_path: str, force: bool = False) -> int:
    """
    Generate missing translation files for a single translations folder

    Reads en.json, translates to all missing languages, writes JSON files.
    Skips languages that already have a file unless force=True.

    @param folder_path (str): Path to the translations/ folder
    @param force (bool): If True, regenerate even if file exists
    @returns int - Number of files generated
    """

    folder = Path(folder_path)
    en_file = folder / "en.json"

    # Check en.json exists
    if not en_file.exists():
        logger.warning(f"No en.json found in {folder_path}, skipping")
        return 0

    # Load English translations
    with open(en_file, encoding="utf-8") as f:
        en_data = json.load(f)

    if not en_data:
        logger.warning(f"Empty en.json in {folder_path}, skipping")
        return 0

    files_generated = 0

    for lang in TARGET_LANGUAGES:
        lang_file = folder / f"{lang}.json"

        # Skip if file already exists (unless force)
        if lang_file.exists() and not force:
            continue

        logger.info(f"  Translating to {lang}...")

        # Translate all values
        translated = translate_values(en_data, lang)

        # Write JSON with sorted keys, 2-space indent, no ASCII escaping
        with open(lang_file, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

        files_generated += 1

        # Small delay to avoid rate limiting
        time.sleep(0.2)

    return files_generated


def find_incomplete_folders(src_root: str) -> list[str]:
    """
    Find all translations/ folders under src_root that are missing language files

    @param src_root (str): Root path to scan (e.g., frontend/vite/src)
    @returns list[str] - List of folder paths that need translation generation
    """

    incomplete = []
    root = Path(src_root)

    for translations_dir in root.rglob("translations"):
        if not translations_dir.is_dir():
            continue

        en_file = translations_dir / "en.json"
        if not en_file.exists():
            continue

        # Check if any target languages are missing
        for lang in TARGET_LANGUAGES:
            if not (translations_dir / f"{lang}.json").exists():
                incomplete.append(str(translations_dir))
                break

    return sorted(incomplete)


#
# Handler Functions
#


def generate_translations(
    folder: Optional[str] = None, force: bool = False, generate_all: bool = False
) -> dict[str, Any]:
    """
    Generate missing translation files

    Generates missing translation files by translating en.json to all target languages.
    Supports generating for a single folder or scanning all incomplete folders.

    @param folder (Optional[str]): Path to a specific translations folder
    @param force (bool): If True, regenerate even if file exists
    @param generate_all (bool): If True, scan and generate for all incomplete folders
    @returns dict[str, Any] - Response with generation results
    """

    logger.info("generate_translations called")

    # Validate: require either folder or all, but not both
    if not folder and not generate_all:
        return {
            "status": "error",
            "message": "Must provide either 'folder' or 'all' parameter",
            "folders_processed": 0,
            "files_generated": 0,
            "details": [],
        }

    if folder and generate_all:
        return {
            "status": "error",
            "message": "Cannot provide both 'folder' and 'all' parameters",
            "folders_processed": 0,
            "files_generated": 0,
            "details": [],
        }

    # Single folder mode
    if folder:
        logger.info(f"Generating translations for: {folder}")
        count = generate_translations_for_folder(folder, force=force)

        return {
            "status": "success",
            "message": f"Generated {count} translation files for {folder}",
            "folders_processed": 1,
            "files_generated": count,
            "details": [{"folder": folder, "files_generated": count}],
        }

    # All incomplete folders mode
    from dev.paths import FRONTEND_SRC
    src_root = FRONTEND_SRC

    logger.info(f"Scanning for incomplete translation folders in {src_root}...")
    folders = find_incomplete_folders(str(src_root))

    # All folders are complete
    if not folders:
        return {
            "status": "success",
            "message": "All translation folders are complete",
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
        f"Done! Generated {total_generated} translation files across {len(folders)} folders"
    )

    return {
        "status": "success",
        "message": f"Generated {total_generated} translation files across {len(folders)} folders",
        "folders_processed": len(folders),
        "files_generated": total_generated,
        "details": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate translation files")
    parser.add_argument("--folder", help="Path to a specific translations folder")
    parser.add_argument("--force", action="store_true", help="Regenerate even if file exists")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="generate_all",
        help="Generate for all incomplete folders",
    )
    args = parser.parse_args()
    result = generate_translations(
        folder=args.folder, force=args.force, generate_all=args.generate_all
    )
    print(json.dumps(result, indent=2))
