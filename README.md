# Docling VLM Sidecar

Lightweight MLX-based document conversion sidecar for macOS applications.

## Overview

This is a standalone executable that uses **mlx-vlm** for Vision-Language Model inference to convert document images to structured formats. Key advantages:

- **Smaller bundle size**: ~200-400MB vs ~1GB for PyTorch-based solutions
- **No PyTorch dependency**: Uses Apple's MLX framework
- **Apple Silicon optimized**: Native arm64, leverages Metal GPU
- **Signed and notarized**: Ready for distribution in macOS apps

## Installation

### From Releases

Download the latest signed and notarized build from [Releases](../../releases).

```bash
# Extract
unzip docling_vlm_sidecar-*.zip

# Verify signature
codesign -dvv docling_vlm_sidecar/docling_vlm_sidecar
```

### Build from Source

Prerequisites:
- **macOS** with Apple Silicon (arm64)
- **uv** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Python 3.11+** (managed by uv)

```bash
# Build the sidecar (first time, includes dependency installation)
./build.sh --sync

# Subsequent builds (uses existing venv)
./build.sh

# Build with APFS compression (~45% smaller)
./build.sh --compress

# Sign for development (ad-hoc)
./sign_sidecar.sh
```

## Usage

The sidecar communicates via stdin/stdout using a JSON protocol.

### Check Model Status

```bash
echo '{"action": "check_models", "model_path": "/path/to/model"}' | ./docling_vlm_sidecar
```

### Convert Image to Document

```bash
# Download test image
curl -sL "https://ibm.biz/docling-page-with-table" -o /tmp/test_doc.png

# Set model path (adjust to your HuggingFace cache location)
MODEL_PATH="$HOME/.cache/huggingface/hub/models--ibm-granite--granite-docling-258M-mlx/snapshots/<hash>"

# Convert to DoclingDocument JSON (default)
(echo "{\"action\": \"convert\", \"model_path\": \"$MODEL_PATH\"}"; cat /tmp/test_doc.png) | ./docling_vlm_sidecar

# Convert to markdown
(echo "{\"action\": \"convert\", \"model_path\": \"$MODEL_PATH\", \"output_format\": \"markdown\"}"; cat /tmp/test_doc.png) | ./docling_vlm_sidecar

# Convert to HTML
(echo "{\"action\": \"convert\", \"model_path\": \"$MODEL_PATH\", \"output_format\": \"html\"}"; cat /tmp/test_doc.png) | ./docling_vlm_sidecar
```

## Response Format

```json
{
  "success": true,
  "format": "docling",
  "data": { ... },
  "metadata": {
    "prompt_tokens": 1142,
    "prompt_tokens_per_sec": 3180.004,
    "generation_tokens": 329,
    "generation_tokens_per_sec": 443.155,
    "peak_memory_gb": 1.496
  },
  "error": null
}
```

| Format | `data` contents |
|--------|-----------------|
| `docling` (default) | Full DoclingDocument JSON structure |
| `markdown` | Markdown string |
| `html` | HTML string |

### Metadata Fields

| Field | Description |
|-------|-------------|
| `prompt_tokens` | Number of tokens in the prompt (including image tokens) |
| `prompt_tokens_per_sec` | Prompt processing speed (prefill phase) |
| `generation_tokens` | Number of tokens generated |
| `generation_tokens_per_sec` | Token generation speed |
| `peak_memory_gb` | Peak GPU memory usage in GB |

## Configuration

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `"check_models"` or `"convert"` |
| `model_path` | string | Path to MLX model directory |
| `output_format` | string | `"docling"` (default), `"markdown"`, or `"html"` |
| `image_mode` | string | `"placeholder"` (default), `"embedded"`, or `"referenced"` |
| `include_page_images` | bool | Include base64 page images in docling output (default: `false`) |
| `document_name` | string | Name for the document (default: "Document") |
| `prompt` | string | Custom prompt for the VLM (default: "Convert this page to docling.") |

## Supported Models

| Model | Repo | Size |
|-------|------|------|
| `granite-docling-258M-mlx` | `ibm-granite/granite-docling-258M-mlx` | ~500 MB |
| `SmolDocling-256M-preview-mlx-bf16` | `docling-project/SmolDocling-256M-preview-mlx-bf16` | ~500 MB |

## GitHub Actions Release Workflow

This repository includes a GitHub Actions workflow for building signed and notarized releases.

### Required Secrets

Configure these secrets in your repository settings:

| Secret | Description |
|--------|-------------|
| `APPLE_CERTIFICATE` | Base64-encoded Developer ID Application certificate (.p12) |
| `APPLE_CERTIFICATE_PASSWORD` | Password for the .p12 file |
| `APPLE_TEAM_ID` | Your Apple Developer Team ID (10 characters) |
| `APPLE_ID` | Apple ID email for notarization |
| `APPLE_APP_PASSWORD` | App-specific password for notarization |

### Setting Up Secrets

1. **Export your Developer ID certificate:**
   ```bash
   # Open Keychain Access, find "Developer ID Application: Your Name"
   # Right-click > Export, save as certificate.p12 with a password

   # Convert to base64
   base64 -i certificate.p12 | pbcopy
   # Paste as APPLE_CERTIFICATE secret
   ```

2. **Create an app-specific password:**
   - Go to https://appleid.apple.com/account/manage
   - Sign in and go to "App-Specific Passwords"
   - Generate a new password for "GitHub Actions"
   - Use this as `APPLE_APP_PASSWORD`

3. **Find your Team ID:**
   ```bash
   # From your certificate
   security find-identity -v -p codesigning | grep "Developer ID"
   # Team ID is in parentheses, e.g., (ABCD1234XY)
   ```

### Triggering a Release

1. Go to Actions > "Build and Release"
2. Click "Run workflow"
3. Enter the version number (e.g., `1.0.0`)
4. Optionally mark as pre-release
5. Click "Run workflow"

The workflow will:
- Build the sidecar with PyInstaller
- Apply APFS compression
- Sign all binaries with your Developer ID
- Submit for Apple notarization
- Staple the notarization ticket
- Create a GitHub release with the signed artifact

## Architecture Notes

- **Apple Silicon only**: MLX requires arm64
- **No UPX**: Compression breaks macOS code signing
- **Console mode**: Required for stdin/stdout IPC
- **Model pre-download**: Models must be downloaded separately by the host application

## License

MIT License - see [LICENSE](LICENSE) for details.
