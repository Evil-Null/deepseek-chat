#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
#  DS Chat — Installer
#  Professional DeepSeek AI Terminal Client
# ═══════════════════════════════════════════════════════════════

INSTALL_DIR="$HOME/Desktop/deepseek-chat"
SYMLINK_PATH="$HOME/.local/bin/dschat"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║        DS Chat — Installer            ║"
echo "  ║   DeepSeek AI Terminal Client v1.0    ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ─── Check Python ───
if ! command -v python3 &>/dev/null; then
    echo "  [ERROR] python3 not found. Install it first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "  [ERROR] Python 3.10+ required. Found: $PY_VERSION"
    exit 1
fi
echo "  [OK] Python $PY_VERSION"

# ─── Check venv module ───
if ! python3 -m venv --help &>/dev/null; then
    echo "  [ERROR] python3-venv not installed."
    echo "  Run: sudo apt install python3-venv"
    exit 1
fi
echo "  [OK] python3-venv"

# ─── Create virtual environment ───
if [ -d "$INSTALL_DIR/.venv" ]; then
    echo "  [OK] Virtual environment exists, recreating..."
    rm -rf "$INSTALL_DIR/.venv"
fi

echo "  [..] Creating virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"
echo "  [OK] Virtual environment created"

# ─── Install dependencies ───
echo "  [..] Installing dependencies..."
source "$INSTALL_DIR/.venv/bin/activate"
pip install --upgrade pip --quiet 2>/dev/null
pip install -e "$INSTALL_DIR" --quiet 2>&1 | tail -1
echo "  [OK] All 9 dependencies installed"

# ─── Setup .env if needed ───
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "  ┌─────────────────────────────────────────┐"
    echo "  │  API Key needed!                         │"
    echo "  │  Edit: $INSTALL_DIR/.env                 │"
    echo "  │  Get key: platform.deepseek.com          │"
    echo "  └─────────────────────────────────────────┘"
    echo ""
    read -p "  Paste your DeepSeek API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        echo "DEEPSEEK_API_KEY=$api_key" > "$INSTALL_DIR/.env"
        echo "  [OK] API key saved"
    else
        echo "  [SKIP] Edit .env later: nano $INSTALL_DIR/.env"
    fi
else
    echo "  [OK] .env exists (keeping current API key)"
fi

# ─── Create global symlink ───
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/dschat" "$SYMLINK_PATH"
chmod +x "$INSTALL_DIR/dschat"
echo "  [OK] Command 'dschat' linked to ~/.local/bin/"

# ─── Check PATH ───
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "  [WARN] ~/.local/bin is not in your PATH."
    echo "  Add this to your ~/.bashrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  Or run directly: ~/Desktop/deepseek-chat/dschat"
fi

# ─── Done ───
echo ""
echo "  ═══════════════════════════════════════"
echo "  Installation complete!"
echo ""
echo "  Run:  dschat"
echo "  Or:   ~/Desktop/deepseek-chat/dschat"
echo "  ═══════════════════════════════════════"
echo ""
