#!/usr/bin/env python3
"""
Docling VLM Sidecar - Lightweight MLX-based document conversion.

This is a minimal sidecar that uses mlx-vlm for Vision-Language Model inference,
without PyTorch dependencies. It converts images to structured documents using
models like granite-docling-258M-mlx.

Protocol:
- stdin: JSON command line, optionally followed by image bytes
- stdout: JSON response
- stderr: Logging

Actions:
- check_models: Check if model exists at specified path
- convert: Convert image bytes to markdown/json using VLM
"""

import io
import json
import logging
import sys
from pathlib import Path

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] docling-vlm-sidecar: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def check_models(config: dict) -> dict:
    """Check if a model exists at the specified path."""
    model_path = config.get("model_path")

    if not model_path:
        return {
            "success": False,
            "error": "model_path is required",
            "data": None,
        }

    path = Path(model_path)

    # Check for key model files that indicate a valid MLX model
    model_exists = path.exists() and path.is_dir()
    has_weights = False
    has_config = False

    if model_exists:
        # MLX models typically have these files
        has_weights = (path / "weights.npz").exists() or any(path.glob("*.safetensors"))
        has_config = (path / "config.json").exists()

    status = {
        "path": str(path),
        "exists": model_exists,
        "has_weights": has_weights,
        "has_config": has_config,
        "ready": model_exists and has_weights and has_config,
    }

    return {
        "success": True,
        "data": {"model": status},
        "error": None,
    }


def convert_image(config: dict, image_bytes: bytes) -> dict:
    """Convert image bytes to document using mlx-vlm."""
    model_path = config.get("model_path")
    output_format = config.get("output_format", "docling")  # docling (default), markdown, html
    document_name = config.get("document_name", "Document")
    prompt = config.get("prompt", "Convert this page to docling.")
    image_mode = config.get("image_mode", "placeholder")  # placeholder (default), embedded, referenced
    include_page_images = config.get("include_page_images", False)  # include base64 page images in docling output

    if not model_path:
        return {
            "success": False,
            "error": "model_path is required",
            "data": None,
        }

    if not image_bytes:
        return {
            "success": False,
            "error": "No image data provided",
            "data": None,
        }

    try:
        # Import heavy dependencies only when needed
        logger.info("Loading dependencies...")
        from PIL import Image
        from docling_core.types.doc.document import DocTagsDocument, DoclingDocument
        from docling_core.types.doc import ImageRefMode
        from mlx_vlm import load, stream_generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config

        # Load image from bytes
        logger.info("Loading image...")
        pil_image = Image.open(io.BytesIO(image_bytes))

        # Ensure RGB mode
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        # Load model
        logger.info(f"Loading model from {model_path}...")
        model, processor = load(model_path)
        mlx_config = load_config(model_path)

        # Prepare prompt
        formatted_prompt = apply_chat_template(processor, mlx_config, prompt, num_images=1)
        logger.info(f"Using prompt: {prompt}")

        # Generate DocTags output using streaming
        logger.info("Generating document structure...")
        output = ""
        last_result = None

        for result in stream_generate(
            model,
            processor,
            formatted_prompt,
            [pil_image],
            max_tokens=4096,
            verbose=False,
        ):
            last_result = result
            output += result.text
            if "</doctag>" in result.text:
                break

        # Extract metadata from the GenerationResult object
        # (includes actual prompt tokens with image tokens expanded)
        metadata = {
            "prompt_tokens": last_result.prompt_tokens if last_result else 0,
            "prompt_tokens_per_sec": round(last_result.prompt_tps, 3) if last_result else 0,
            "generation_tokens": last_result.generation_tokens if last_result else 0,
            "generation_tokens_per_sec": round(last_result.generation_tps, 3) if last_result else 0,
            "peak_memory_gb": round(last_result.peak_memory, 3) if last_result else 0,
        }

        logger.info(f"Generated {len(output)} characters ({metadata['generation_tokens']} tokens)")
        logger.info(f"Prompt: {metadata['prompt_tokens']} tokens, {metadata['prompt_tokens_per_sec']:.1f} t/s | Generation: {metadata['generation_tokens']} tokens, {metadata['generation_tokens_per_sec']:.1f} t/s | Peak memory: {metadata['peak_memory_gb']:.3f} GB")

        # Parse the output - find content between doctags
        doctags_content = output
        if "</doctag>" in output:
            doctags_content = output.split("</doctag>")[0] + "</doctag>"

        logger.info("Creating DoclingDocument...")

        # Create DoclingDocument from generated DocTags
        doctags_doc = DocTagsDocument.from_doctags_and_image_pairs(
            [doctags_content], [pil_image]
        )
        doc = DoclingDocument.load_from_doctags(doctags_doc, document_name=document_name)

        # Map image_mode string to ImageRefMode enum
        # Note: VLM detects figures but doesn't extract them as separate images.
        # The pictures array will be empty, so all modes effectively show placeholders.
        image_ref_mode = {
            "placeholder": ImageRefMode.PLACEHOLDER,
            "embedded": ImageRefMode.EMBEDDED,
            "referenced": ImageRefMode.REFERENCED,
        }.get(image_mode.lower(), ImageRefMode.PLACEHOLDER)

        # Export based on format
        if output_format == "markdown":
            content = doc.export_to_markdown(image_mode=image_ref_mode)
        elif output_format == "html":
            content = doc.export_to_html(image_mode=image_ref_mode)
        else:  # docling (default) - full DoclingDocument as JSON dict
            content = doc.export_to_dict()
            # Strip large base64 page images if not requested
            if not include_page_images and "pages" in content:
                for page_key, page_data in content["pages"].items():
                    if "image" in page_data:
                        # Keep metadata but remove the large base64 uri
                        page_data["image"].pop("uri", None)

        logger.info(f"Conversion complete (format: {output_format})")

        return {
            "success": True,
            "format": output_format,
            "data": content,
            "metadata": metadata,
            "error": None,
        }

    except Exception as e:
        logger.exception("Conversion failed")
        return {
            "success": False,
            "error": str(e),
            "data": None,
        }


def main():
    """Main entry point for the sidecar."""
    logger.info("Docling VLM sidecar starting...")

    # Read command from stdin
    try:
        command_line = sys.stdin.buffer.readline()
        if not command_line:
            logger.error("Empty stdin - no command received")
            print(json.dumps({
                "success": False,
                "error": "No command received",
                "data": None,
            }))
            sys.exit(1)

        command = json.loads(command_line.decode("utf-8").strip())
        logger.info(f"Received command: {command.get('action', 'unknown')}")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON command: {e}")
        print(json.dumps({
            "success": False,
            "error": f"Invalid JSON: {e}",
            "data": None,
        }))
        sys.exit(1)

    action = command.get("action")

    if action == "check_models":
        result = check_models(command)

    elif action == "convert":
        # Read remaining stdin as image bytes
        image_bytes = sys.stdin.buffer.read()
        logger.info(f"Read {len(image_bytes)} bytes of image data")
        result = convert_image(command, image_bytes)

    else:
        result = {
            "success": False,
            "error": f"Unknown action: {action}",
            "data": None,
        }

    # Output result as JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
