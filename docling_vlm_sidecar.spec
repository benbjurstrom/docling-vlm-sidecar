# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Docling VLM-only sidecar binary.

Build with:
    pyinstaller docling_vlm_sidecar.spec

This creates a lightweight directory bundle at dist/docling_vlm_sidecar/
that uses MLX instead of PyTorch for VLM inference.

Key differences from full sidecar:
- No PyTorch (uses MLX for inference)
- No OCR or table structure models
- Image-only input (no PDF support)
- Significantly smaller bundle size

Target: Apple Silicon (arm64) only
"""

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
)
import sys

block_cipher = None

# -----------------------------------------------------------------------------
# Dependency Collection
# -----------------------------------------------------------------------------

hidden_imports = []
datas = []
binaries = []

# Collect docling_core (document structure/export only)
docling_core_datas, docling_core_binaries, docling_core_hidden = collect_all('docling_core')
datas += docling_core_datas
binaries += docling_core_binaries
hidden_imports += docling_core_hidden

# Collect MLX packages (Apple Silicon ML framework - the core of this sidecar)
try:
    mlx_datas, mlx_binaries, mlx_hidden = collect_all('mlx')
    datas += mlx_datas
    binaries += mlx_binaries
    hidden_imports += mlx_hidden
except Exception as e:
    print(f"Warning: Could not collect mlx: {e}")

try:
    mlx_vlm_datas, mlx_vlm_binaries, mlx_vlm_hidden = collect_all('mlx_vlm')
    datas += mlx_vlm_datas
    binaries += mlx_vlm_binaries
    hidden_imports += mlx_vlm_hidden
except Exception as e:
    print(f"Warning: Could not collect mlx_vlm: {e}")

# Collect pydantic (data validation for docling_core)
try:
    pydantic_datas, pydantic_binaries, pydantic_hidden = collect_all('pydantic')
    datas += pydantic_datas
    binaries += pydantic_binaries
    hidden_imports += pydantic_hidden
except Exception as e:
    print(f"Warning: Could not collect pydantic: {e}")

# Collect huggingface_hub (for model loading)
try:
    hf_datas, hf_binaries, hf_hidden = collect_all('huggingface_hub')
    datas += hf_datas
    binaries += hf_binaries
    hidden_imports += hf_hidden
except Exception as e:
    print(f"Warning: Could not collect huggingface_hub: {e}")

# Collect transformers (required by mlx_vlm for tokenizers/configs)
try:
    hidden_imports += collect_submodules('transformers')
except Exception as e:
    print(f"Warning: Could not collect transformers: {e}")

# Additional hidden imports
hidden_imports += [
    # Image processing
    'PIL',
    'PIL.Image',
    'numpy',
    # Model loading
    'safetensors',
    'tokenizers',
    # Common utilities
    'regex',
    'filelock',
    'requests',
    'tqdm',
    'yaml',
    'packaging',
    # Transformers auto classes (needed for mlx_vlm)
    'transformers.models.auto.modeling_auto',
    'transformers.models.auto.processing_auto',
    'transformers.models.auto.configuration_auto',
    'transformers.models.auto.tokenization_auto',
    'transformers.models.auto.image_processing_auto',
]

# -----------------------------------------------------------------------------
# Exclusions (CRITICAL: exclude PyTorch to keep bundle small)
# -----------------------------------------------------------------------------

excludes = [
    # PyTorch and related (THE MAIN SIZE SAVINGS)
    'torch',
    'torchvision',
    'torchaudio',
    'torch._C',
    'torch._dynamo',
    'torch.cuda',
    # Nvidia/CUDA binaries
    'nvidia',
    'triton',
    'tensorrt',
    # Full docling (we only need docling_core)
    'docling',
    'docling_ibm_models',
    'docling_parse',
    # OCR (not needed for VLM-only)
    'ocrmac',
    'pypdfium2',
    # PyObjC (not needed without ocrmac)
    'objc',
    'Foundation',
    'Quartz',
    'Vision',
    'pyobjc',
    # GUI toolkits
    'tkinter',
    'Qt5',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'wx',
    'gtk',
    # Visualization
    'matplotlib',
    'plotly',
    'bokeh',
    'seaborn',
    # Development tools
    'pytest',
    'sphinx',
    'IPython',
    'jupyter',
    'notebook',
    # Heavy unused packages
    'scipy',
    'sympy',
]

# -----------------------------------------------------------------------------
# Analysis
# -----------------------------------------------------------------------------

a = Analysis(
    ['sidecar_main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# -----------------------------------------------------------------------------
# PYZ Archive
# -----------------------------------------------------------------------------

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# -----------------------------------------------------------------------------
# Executable
# -----------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='docling_vlm_sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols
    upx=False,   # UPX breaks code signing on macOS
    console=True,  # Required for stdin/stdout IPC
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',  # Apple Silicon only (required for MLX)
    codesign_identity=None,
    entitlements_file=None,
)

# -----------------------------------------------------------------------------
# Collect (creates directory bundle)
# -----------------------------------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='docling_vlm_sidecar',
)
