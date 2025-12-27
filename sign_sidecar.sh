#!/bin/bash
#
# sign_sidecar.sh - Code sign the VLM sidecar bundle
#
# Signs all executables, libraries, and frameworks in the sidecar
# bundle for running within a sandboxed macOS app.
#
# Usage:
#   ./sign_sidecar.sh                    # Ad-hoc signing (development)
#   ./sign_sidecar.sh "Developer ID Application: ..."  # Production signing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SIDECAR_DIR="$SCRIPT_DIR/dist/docling_vlm_sidecar"
INTERNAL_DIR="$SIDECAR_DIR/_internal"

# Default to ad-hoc signing if no identity provided
IDENTITY="${1:--}"

if [ ! -d "$SIDECAR_DIR" ]; then
    echo "Error: Sidecar not found at $SIDECAR_DIR"
    echo "Run ./build.sh first to create the sidecar bundle."
    exit 1
fi

echo "Signing VLM sidecar bundle with identity: $IDENTITY"
echo "Sidecar location: $SIDECAR_DIR"
echo ""

# Clear extended attributes to prevent Team ID conflicts
echo "Clearing extended attributes..."
xattr -cr "$SIDECAR_DIR"

# Count files to sign
DYLIB_COUNT=$(find "$INTERNAL_DIR" -name "*.dylib" 2>/dev/null | wc -l | tr -d ' ')
SO_COUNT=$(find "$INTERNAL_DIR" -name "*.so" 2>/dev/null | wc -l | tr -d ' ')
echo "Found $DYLIB_COUNT .dylib files and $SO_COUNT .so files to sign"
echo ""

# Sign all .dylib files
echo "Signing .dylib files..."
find "$INTERNAL_DIR" -name "*.dylib" -exec codesign --force --sign "$IDENTITY" --timestamp=none {} \; 2>/dev/null || true

# Sign all .so files (Python extensions)
echo "Signing .so files..."
find "$INTERNAL_DIR" -name "*.so" -exec codesign --force --sign "$IDENTITY" --timestamp=none {} \; 2>/dev/null || true

# Sign any frameworks
echo "Signing frameworks..."
find "$INTERNAL_DIR" -name "*.framework" -type d -exec codesign --force --deep --sign "$IDENTITY" --timestamp=none {} \; 2>/dev/null || true

# Sign the Python library if present
if ls "$INTERNAL_DIR"/libpython*.dylib 1> /dev/null 2>&1; then
    echo "Signing Python library..."
    codesign --force --sign "$IDENTITY" --timestamp=none "$INTERNAL_DIR"/libpython*.dylib 2>/dev/null || true
fi

# Sign the main executable last with entitlements
echo "Signing main executable with entitlements..."
ENTITLEMENTS="$SCRIPT_DIR/sidecar.entitlements"
if [ -f "$ENTITLEMENTS" ]; then
    codesign --force --sign "$IDENTITY" --timestamp=none --entitlements "$ENTITLEMENTS" "$SIDECAR_DIR/docling_vlm_sidecar"
else
    codesign --force --sign "$IDENTITY" --timestamp=none "$SIDECAR_DIR/docling_vlm_sidecar"
fi

echo ""
echo "Signing complete!"

# Verify the main executable signature
echo ""
echo "Verifying signature..."
codesign -dvv "$SIDECAR_DIR/docling_vlm_sidecar" 2>&1 | head -5

echo ""
echo "Done. The VLM sidecar bundle is now signed."
