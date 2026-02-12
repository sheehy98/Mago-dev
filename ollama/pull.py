#
# Imports
#

# Standard library
import argparse
import json
import logging
import subprocess
from typing import Any

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def pull_model(models: str) -> dict[str, Any]:
    """
    Pull Ollama models

    @param models (str): Comma-separated list of model names
    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("pull_model called")

    # Validate models parameter
    if not models:
        return {"error": "Must provide 'models' parameter"}

    # Split comma-separated models
    model_list = [m.strip() for m in models.split(",") if m.strip()]

    if not model_list:
        return {"error": "No valid models specified"}

    # Pull each model
    results = []
    success_count = 0

    for model in model_list:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode == 0:
            results.append({"model": model, "status": "success"})
            success_count += 1
        else:
            results.append({"model": model, "status": "failed", "error": result.stderr})

    logger.info(f"pull_model completed: {success_count}/{len(model_list)} models pulled")
    return {
        "status": "success" if success_count == len(model_list) else "partial",
        "message": f"Pulled {success_count}/{len(model_list)} models",
        "models_pulled": success_count,
        "total_models": len(model_list),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull Ollama models")
    parser.add_argument("--models", required=True, help="Comma-separated list of models")
    args = parser.parse_args()
    result = pull_model(models=args.models)
    print(json.dumps(result, indent=2))
