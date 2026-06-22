#!/usr/bin/env bash
#
# install.sh — CodeTwin Analyzer
#
# Instalação completa e assertiva para Ubuntu.
# Cria venv, instala dependências Python, PMD e o projeto.
#
# Uso:
#     chmod +x install.sh && ./install.sh
#
set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Guardas de ambiente
# ---------------------------------------------------------------------------
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "ERRO: Este script só suporta Linux (Ubuntu). Abortando." >&2
    exit 1
fi

if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    if [[ "${ID:-}" != "ubuntu" ]]; then
        echo "AVISO: Este script foi feito para Ubuntu. Distro detectada: $ID. Continuando assim mesmo..." >&2
    fi
fi

# ---------------------------------------------------------------------------
# 2. Constantes
# ---------------------------------------------------------------------------
PMD_VERSION="7.0.0"
PMD_URL="https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip"
PMD_INSTALL_DIR="/opt/pmd"
PMD_BIN_DIR="${PMD_INSTALL_DIR}/pmd-bin-${PMD_VERSION}/bin"

PYTHON_MIN_VERSION="3.9"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# ---------------------------------------------------------------------------
# 3. Funções de utilidade
# ---------------------------------------------------------------------------
verlte() {
    # "version less than or equal" — compara semântica simples
    printf '%s\n%s' "$1" "$2" | sort -V -C
}

die() {
    echo "ERRO: $*" >&2
    exit 1
}

step() {
    echo ""
    echo "==> $*"
    echo "    $(date '+%H:%M:%S')"
}

ok() {
    echo "    ✓ $*"
}

# ---------------------------------------------------------------------------
# 4. Dependências de sistema (apt)
# ---------------------------------------------------------------------------
step "Instalando dependências de sistema..."

sudo apt-get update -qq

# PMD 7.x requer Java 8+ (JRE é suficiente)
# python3 + venv (garantia)
# unzip → extrair PMD, curl → baixar PMD
sudo apt-get install -y -qq \
    default-jre-headless \
    python3 \
    python3-pip \
    python3-venv \
    unzip \
    curl

ok "Pacotes de sistema instalados."
echo "    Java:   $(java -version 2>&1 | head -1 || echo 'N/D')"
echo "    Python: $(python3 --version)"

# ---------------------------------------------------------------------------
# 5. Verificação da versão do Python
# ---------------------------------------------------------------------------
step "Verificando versão do Python..."

PY_ACTUAL=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if verlte "$PYTHON_MIN_VERSION" "$PY_ACTUAL"; then
    ok "Python $PY_ACTUAL >= $PYTHON_MIN_VERSION ✓"
else
    die "Python $PY_ACTUAL é inferior ao mínimo exigido ($PYTHON_MIN_VERSION)."
fi

# ---------------------------------------------------------------------------
# 6. Instalação do PMD (sistema)
# ---------------------------------------------------------------------------
step "Instalando PMD ${PMD_VERSION}..."

if [[ -x "${PMD_BIN_DIR}/pmd" ]]; then
    ok "PMD já instalado em ${PMD_BIN_DIR}/pmd"
else
    sudo mkdir -p "${PMD_INSTALL_DIR}"

    TMP_ZIP="$(mktemp /tmp/pmd-XXXXXX.zip)"
    curl -fsSL "${PMD_URL}" -o "${TMP_ZIP}" || die "Falha ao baixar PMD de ${PMD_URL}"
    ok "PMD ZIP baixado."

    sudo unzip -qo "${TMP_ZIP}" -d "${PMD_INSTALL_DIR}"
    rm -f "${TMP_ZIP}"

    if [[ -x "${PMD_BIN_DIR}/pmd" ]]; then
        ok "PMD extraído em ${PMD_BIN_DIR}"
    else
        die "PMD extraído mas binário não encontrado em ${PMD_BIN_DIR}/pmd"
    fi

    # Torna executável se necessário
    sudo chmod +x "${PMD_BIN_DIR}/pmd" 2>/dev/null || true
fi

# Adiciona ao PATH permanentemente via /etc/profile.d se ainda não estiver
PMD_PROFILE_D="/etc/profile.d/codetwin-pmd.sh"
if [[ ! -f "${PMD_PROFILE_D}" ]]; then
    echo "export PATH=\"${PMD_BIN_DIR}:\$PATH\"" | sudo tee "${PMD_PROFILE_D}" > /dev/null
    ok "PMD adicionado ao PATH do sistema em ${PMD_PROFILE_D}"
fi

# Também adiciona ao PATH da sessão atual
export PATH="${PMD_BIN_DIR}:${PATH}"

# Verifica se funciona
pmd --version >/dev/null 2>&1 && ok "PMD funcional: $(pmd --version 2>&1 | head -1)" \
    || die "PMD não executa. Verifique a instalação do Java (java -version)."

# ---------------------------------------------------------------------------
# 7. Virtual environment Python
# ---------------------------------------------------------------------------
step "Criando virtual environment em ${VENV_DIR}..."

if [[ -d "${VENV_DIR}" ]]; then
    ok "venv já existe em ${VENV_DIR}"
else
    python3 -m venv "${VENV_DIR}" || die "Falha ao criar venv."
    ok "venv criado."
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

ok "venv ativado."
echo "    python = $(which python)"
echo "    pip    = $(which pip)"

# ---------------------------------------------------------------------------
# 8. Dependências Python
# ---------------------------------------------------------------------------
step "Instalando dependências Python..."

pip install --upgrade pip -q
pip install -r "${SCRIPT_DIR}/requirements.txt" -q
pip install pytest flake8 -q
pip install -e "${SCRIPT_DIR}" -q

ok "Pacotes Python instalados:"
pip freeze | grep -E '^(requests|python-dotenv|fire|pytest|flake8|codetwin)' | while read -r pkg; do
    echo "    ${pkg}"
done

# ---------------------------------------------------------------------------
# 9. Verificação final
# ---------------------------------------------------------------------------
step "Verificação final..."

FAILS=0

# PMD no PATH
if command -v pmd &>/dev/null; then
    ok "pmd ......... OK ($(command -v pmd))"
else
    echo "    ✗ pmd ......... NÃO ENCONTRADO NO PATH" >&2
    ((FAILS++))
fi

# Python imports
for mod in requests dotenv fire codetwin_analyzer; do
    if python -c "import ${mod}" 2>/dev/null; then
        ok "import ${mod} ... OK"
    else
        echo "    ✗ import ${mod} ... FALHOU" >&2
        ((FAILS++))
    fi
done

# ---------------------------------------------------------------------------
# 10. Resultado
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
if [[ $FAILS -eq 0 ]]; then
    echo "Instalação concluída com sucesso!"
    echo ""
    echo "Para ativar o ambiente:"
    echo "    source ${VENV_DIR}/bin/activate"
    echo ""
    echo "Para rodar os testes:"
    echo "    pytest tests/ -v"
    echo "============================================================"
else
    echo "Instalação concluída com ${FAILS} falha(s)."
    echo "Verifique as mensagens acima e corrija antes de prosseguir."
    echo "============================================================"
    exit 1
fi
