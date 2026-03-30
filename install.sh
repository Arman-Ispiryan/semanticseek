#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh  —  SemanticSeek installer
# curl -fsSL https://raw.githubusercontent.com/Arman-Ispiryan/semanticseek/main/install.sh | bash
# ─────────────────────────────────────────────────────────────────────────────
set -e

REPO="https://github.com/Arman-Ispiryan/semanticseek"
INSTALL_DIR="$HOME/.semanticseek"
VENV_DIR="$INSTALL_DIR/venv"
BIN_LINK="/usr/local/bin/semanticseek"

# ── Colours ───────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[semanticseek]${RESET} $*"; }
success() { echo -e "${GREEN}[✔]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
die()     { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${BOLD}${CYAN}  ███████╗███████╗███╗   ███╗ █████╗ ███╗   ██╗████████╗██╗ ██████╗${RESET}"
echo -e "${BOLD}${CYAN}  ██╔════╝██╔════╝████╗ ████║██╔══██╗████╗  ██║╚══██╔══╝██║██╔════╝${RESET}"
echo -e "${BOLD}${CYAN}  ███████╗█████╗  ██╔████╔██║███████║██╔██╗ ██║   ██║   ██║██║     ${RESET}"
echo -e "${BOLD}${CYAN}  ╚════██║██╔══╝  ██║╚██╔╝██║██╔══██║██║╚██╗██║   ██║   ██║██║     ${RESET}"
echo -e "${BOLD}${CYAN}  ███████║███████╗██║ ╚═╝ ██║██║  ██║██║ ╚████║   ██║   ██║╚██████╗${RESET}"
echo -e "${BOLD}${CYAN}  ╚══════╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝${RESET}"
echo ""
echo -e "${DIM}  Natural language file search · Local embeddings${RESET}"
echo -e "${DIM}  ─────────────────────────────────────────────────${RESET}"
echo ""

# ── Arrow-key selector ────────────────────────────────────────────────────────
arrow_select() {
    local prompt="$1"
    shift
    local options=("$@")
    local count=${#options[@]}
    local current=0

    tput civis 2>/dev/null || true
    echo -e "  ${BOLD}$prompt${RESET}"
    echo ""

    _draw_menu() {
        for i in "${!options[@]}"; do
            if [ "$i" -eq "$current" ]; then
                echo -e "    ${CYAN}▶  ${BOLD}${options[$i]}${RESET}"
            else
                echo -e "    ${DIM}   ${options[$i]}${RESET}"
            fi
        done
    }

    _draw_menu

    while true; do
        tput cuu "$count" 2>/dev/null || true

        IFS= read -rsn1 key </dev/tty 2>/dev/null
        if [[ "$key" == $'\x1b' ]]; then
            IFS= read -rsn2 key2 </dev/tty 2>/dev/null
            key="$key$key2"
        fi

        case "$key" in
            $'\x1b[A'|$'\x1b[D')
                (( current-- )) || true
                [ "$current" -lt 0 ] && current=$(( count - 1 ))
                ;;
            $'\x1b[B'|$'\x1b[C')
                (( current++ )) || true
                [ "$current" -ge "$count" ] && current=0
                ;;
            '')
                break
                ;;
        esac

        _draw_menu
    done

    tput cnorm 2>/dev/null || true
    echo ""
    SELECTED_INDEX=$current
}

# ── Device selection ──────────────────────────────────────────────────────────
arrow_select "Select compute device for embeddings:" \
    "CPU  —  Safe, works everywhere, no GPU needed" \
    "GPU  —  Faster, requires CUDA-compatible GPU"

if [ "$SELECTED_INDEX" -eq 0 ]; then
    DEVICE="cpu"
    success "Using CPU"
else
    DEVICE="cuda"
    success "Using GPU (CUDA)"
fi
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
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

# ── Check pip / venv ──────────────────────────────────────────────────────────
if ! python3 -m venv --help &>/dev/null; then
    warn "python3-venv not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y python3-venv python3-pip -qq
    else
        die "Please install python3-venv manually."
    fi
fi

# ── Create install directory ───────────────────────────────────────────────────
info "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"

# ── Clone or download source ───────────────────────────────────────────────────
SRC_DIR="$INSTALL_DIR/src"

if command -v git &>/dev/null; then
    if [ -d "$SRC_DIR/.git" ]; then
        info "Updating existing installation..."
        git -C "$SRC_DIR" reset --hard --quiet
        git -C "$SRC_DIR" pull --quiet
    else
        info "Cloning repository..."
        git clone --quiet "$REPO" "$SRC_DIR"
    fi
else
    warn "git not found, downloading tarball..."
    TARBALL="$INSTALL_DIR/semanticseek.tar.gz"
    curl -fsSL "${REPO}/archive/refs/heads/main.tar.gz" -o "$TARBALL"
    mkdir -p "$SRC_DIR"
    tar -xzf "$TARBALL" -C "$SRC_DIR" --strip-components=1
    rm "$TARBALL"
fi

# ── Save device choice ────────────────────────────────────────────────────────
echo "$DEVICE" > "$INSTALL_DIR/device"
info "Device preference saved: $DEVICE"

# ── Create virtualenv ─────────────────────────────────────────────────────────
info "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet

# ── Install package ───────────────────────────────────────────────────────────
info "Installing SemanticSeek and dependencies (this may take a minute)..."
"$VENV_DIR/bin/pip" install "$SRC_DIR" --quiet

# ── Create launcher (injects SEMANTICSEEK_DEVICE env var) ────────────────────
LAUNCHER="$INSTALL_DIR/semanticseek"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
export SEMANTICSEEK_DEVICE="\$(cat "$INSTALL_DIR/device" 2>/dev/null || echo cpu)"
exec "$VENV_DIR/bin/semanticseek" "\$@"
EOF
chmod +x "$LAUNCHER"

# ── Symlink to /usr/local/bin ──────────────────────────────────────────────────
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
    sudo ln -sf "$LAUNCHER" "$BIN_LINK"
    success "Linked to $BIN_LINK"
else
    warn "Could not write to /usr/local/bin. Adding to PATH manually..."
    SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
    grep -qxF "export PATH=\"$INSTALL_DIR:\$PATH\"" "$SHELL_RC" 2>/dev/null || \
        echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$SHELL_RC"
    warn "Added $INSTALL_DIR to PATH in $SHELL_RC"
    warn "Run: source $SHELL_RC"
fi

echo ""
echo -e "${BOLD}${GREEN}  ✔  SemanticSeek installed!  [device: ${DEVICE}]${RESET}"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo -e "    ${CYAN}semanticseek index ~/Documents${RESET}         # index a folder"
echo -e "    ${CYAN}semanticseek search \"budget report Q3\"${RESET}   # search naturally"
echo -e "    ${CYAN}semanticseek status${RESET}                     # show index stats"
echo -e "    ${CYAN}semanticseek --help${RESET}                     # full help"
echo ""
echo -e "  ${BOLD}Note:${RESET} First run will download the embedding model (~90MB)."
echo ""