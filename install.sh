#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh  —  SemanticSeek installer
# curl -fsSL https://raw.githubusercontent.com/Arman-Ispiryan/semanticseek/main/install.sh | bash
# ─────────────────────────────────────────────────────────────────────────────
set -e

REPO="https://github.com/Arman-Ispiryan/semanticseek"
RAW="https://raw.githubusercontent.com/Arman-Ispiryan/semanticseek/main"
INSTALL_DIR="$HOME/.semanticseek"
VENV_DIR="$INSTALL_DIR/venv"
BIN_LINK="/usr/local/bin/semanticseek"

# ── Colours ──────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[semanticseek]${RESET} $*"; }
success() { echo -e "${GREEN}[✔]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
die()     { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }

echo ""
echo -e "${BOLD}${CYAN}  SemanticSeek — Natural Language File Search${RESET}"
echo -e "${CYAN}  ─────────────────────────────────────────────${RESET}"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    die "Python 3 is required but not found. Install it with: sudo apt install python3"
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    die "Python 3.9+ required, found Python $PY_VER"
fi
info "Python $PY_VER found"

# ── Check pip / venv ─────────────────────────────────────────────────────────
if ! python3 -m venv --help &>/dev/null; then
    warn "python3-venv not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y python3-venv python3-pip -qq
    else
        die "Please install python3-venv manually."
    fi
fi

# ── Create install directory ──────────────────────────────────────────────────
info "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"

# ── Clone or download source ─────────────────────────────────────────────────
SRC_DIR="$INSTALL_DIR/src"

if command -v git &>/dev/null; then
    if [ -d "$SRC_DIR/.git" ]; then
        info "Updating existing installation..."
        git -C "$SRC_DIR" pull --quiet
    else
        info "Cloning repository..."
        git clone --quiet "$REPO" "$SRC_DIR"
    fi
else
    # Fallback: download tarball
    warn "git not found, downloading tarball..."
    TARBALL="$INSTALL_DIR/semanticseek.tar.gz"
    curl -fsSL "${REPO}/archive/refs/heads/main.tar.gz" -o "$TARBALL"
    mkdir -p "$SRC_DIR"
    tar -xzf "$TARBALL" -C "$SRC_DIR" --strip-components=1
    rm "$TARBALL"
fi

# ── Create virtualenv ─────────────────────────────────────────────────────────
info "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet

# ── Install package ───────────────────────────────────────────────────────────
info "Installing SemanticSeek and dependencies (this may take a minute)..."
"$VENV_DIR/bin/pip" install "$SRC_DIR" --quiet

# ── Create launcher script ────────────────────────────────────────────────────
LAUNCHER="$INSTALL_DIR/semanticseek"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
exec "$VENV_DIR/bin/semanticseek" "\$@"
EOF
chmod +x "$LAUNCHER"

# ── Symlink to /usr/local/bin ─────────────────────────────────────────────────
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
    sudo ln -sf "$LAUNCHER" "$BIN_LINK"
    success "Linked to $BIN_LINK"
else
    warn "Could not write to /usr/local/bin. Adding to PATH manually..."
    SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$SHELL_RC"
    warn "Added $INSTALL_DIR to PATH in $SHELL_RC"
    warn "Run: source $SHELL_RC"
fi

# ── Download model in background hint ────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}  ✔  SemanticSeek installed successfully!${RESET}"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo -e "    ${CYAN}semanticseek index ~/Documents${RESET}        # index a folder"
echo -e "    ${CYAN}semanticseek search \"budget report Q3\"${RESET}  # search naturally"
echo -e "    ${CYAN}semanticseek status${RESET}                    # show index stats"
echo -e "    ${CYAN}semanticseek --help${RESET}                    # full help"
echo ""
echo -e "  ${BOLD}Note:${RESET} First run will download the embedding model (~90MB)."
echo ""
