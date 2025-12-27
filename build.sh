#!/bin/bash
#
# Build script for Docling VLM-only sidecar
#
# Creates a lightweight Python bundle using MLX instead of PyTorch.
# This produces a significantly smaller bundle than the full sidecar.
#
# Prerequisites:
#   - uv (install with: curl -LsSf https://astral.sh/uv/install.sh | sh)
#   - Apple Silicon Mac (arm64)
#
# Usage:
#   ./build.sh [--clean] [--sync] [--compress]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
CLEAN=false
SYNC=false
COMPRESS=false

for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN=true
            shift
            ;;
        --sync)
            SYNC=true
            shift
            ;;
        --compress)
            COMPRESS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--clean] [--sync] [--compress]"
            echo ""
            echo "Options:"
            echo "  --clean     Remove build artifacts before building"
            echo "  --sync      Sync dependencies with uv before building"
            echo "  --compress  Apply APFS transparent compression"
            echo ""
            echo "This builds a lightweight VLM-only sidecar using MLX."
            echo "Expected bundle size: ~200-400MB (vs ~1GB for full sidecar)"
            exit 0
            ;;
    esac
done

# Check for uv
if ! command -v uv &> /dev/null; then
    log_error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
log_info "Found uv: $(uv --version)"

# Check architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    log_error "This sidecar requires Apple Silicon (arm64). Current architecture: $ARCH"
    exit 1
fi

# Clean if requested
if [[ "$CLEAN" == true ]]; then
    log_info "Cleaning build artifacts..."
    rm -rf build/ dist/ __pycache__/ *.spec.tmp .venv/
fi

# Create/sync virtual environment
if [[ "$SYNC" == true ]] || [[ ! -d ".venv" ]]; then
    log_info "Creating virtual environment..."
    uv venv --python ">=3.11"

    log_info "Installing dependencies with uv..."
    # Explicitly install WITHOUT torch
    uv pip install -r requirements.txt

    # Verify torch is NOT installed
    if .venv/bin/python -c "import torch" 2>/dev/null; then
        log_warn "PyTorch was installed as a dependency. Bundle may be larger than expected."
        log_info "Consider using --no-deps for specific packages if torch isn't needed."
    else
        log_info "Confirmed: PyTorch NOT installed (using MLX only)"
    fi
fi

# Activate venv for the build
source .venv/bin/activate

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
log_info "Using Python $PYTHON_VERSION"

# Verify MLX is available
if ! python -c "import mlx" 2>/dev/null; then
    log_error "MLX not found. Run with --sync to install dependencies."
    exit 1
fi
log_info "MLX available"

# Verify PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    log_error "PyInstaller not found. Run with --sync to install dependencies."
    exit 1
fi

# Build the sidecar
log_info "Building VLM sidecar with PyInstaller..."
log_info "This should take 1-3 minutes..."
log_info "Detailed log: build/pyinstaller.log"

mkdir -p build
pyinstaller \
    --noconfirm \
    --log-level WARN \
    docling_vlm_sidecar.spec > build/pyinstaller.log 2>&1

BUILD_STATUS=$?
if [[ $BUILD_STATUS -ne 0 ]]; then
    log_error "PyInstaller failed. Last 50 lines of log:"
    tail -50 build/pyinstaller.log
    exit 1
fi

# Check build result
if [[ -d "dist/docling_vlm_sidecar" ]]; then
    log_info "Build successful!"

    # Show bundle size
    BUNDLE_SIZE=$(du -sh dist/docling_vlm_sidecar | cut -f1)
    log_info "Bundle size: $BUNDLE_SIZE"

    # Show main executable
    if [[ -f "dist/docling_vlm_sidecar/docling_vlm_sidecar" ]]; then
        log_info "Executable: dist/docling_vlm_sidecar/docling_vlm_sidecar"

        # Verify it's arm64
        BUNDLE_ARCH=$(file dist/docling_vlm_sidecar/docling_vlm_sidecar | grep -o 'arm64\|x86_64' | head -1)
        log_info "Architecture: $BUNDLE_ARCH"
    else
        log_error "Main executable not found!"
        exit 1
    fi

    # Apply APFS transparent compression if requested
    if [[ "$COMPRESS" == true ]]; then
        echo ""
        log_info "Applying APFS transparent compression..."

        COMPRESSED_DIR="dist/docling_vlm_sidecar_compressed"
        rm -rf "$COMPRESSED_DIR"
        ditto --hfsCompression dist/docling_vlm_sidecar "$COMPRESSED_DIR"

        rm -rf dist/docling_vlm_sidecar
        mv "$COMPRESSED_DIR" dist/docling_vlm_sidecar

        COMPRESSED_SIZE=$(du -sh dist/docling_vlm_sidecar | cut -f1)
        log_info "Compressed size: $COMPRESSED_SIZE (was $BUNDLE_SIZE)"
    fi

    echo ""
    log_info "Next steps:"
    echo "  1. Run ./sign_sidecar.sh to sign the bundle"
    echo "  2. Test with: echo '{\"action\": \"check_models\", \"model_path\": \"/path/to/model\"}' | ./dist/docling_vlm_sidecar/docling_vlm_sidecar"
else
    log_error "Build failed - dist/docling_vlm_sidecar not found"
    exit 1
fi
