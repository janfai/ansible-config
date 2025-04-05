#!/bin/bash
# bootstrap-vm-mint.sh

set -euo pipefail

# Adresáře
ANSIBLE_DIR="/var/lib/ansible"
VAULT_PASS_FILE="$ANSIBLE_DIR/.vault_pass"
BOOTSTRAP_FLAG="$ANSIBLE_DIR/bootstrap_completed"

# Kontrola, zda již bootstrap nebyl spuštěn
if [ -f "$BOOTSTRAP_FLAG" ]; then
    echo "Bootstrap již byl úspěšně dokončen. Pro opětovné spuštění nejprve odstraňte $BOOTSTRAP_FLAG"
    exit 0
fi

# Instalace závislostí
sudo apt update && sudo apt install -y git ansible

# Vytvoření adresářů
sudo mkdir -p "$ANSIBLE_DIR"
sudo chmod 750 "$ANSIBLE_DIR"

# Získání hesla pro Vault (pouze při prvním spuštění)
if [ ! -f "$VAULT_PASS_FILE" ]; then
    echo "Zadejte heslo pro Ansible Vault (nebude zobrazeno):"
    read -s -r VAULT_PASS
    echo "Zadejte heslo znovu pro ověření:"
    read -s -r VAULT_PASS_CONFIRM

    if [ "$VAULT_PASS" != "$VAULT_PASS_CONFIRM" ]; then
        echo "Chyba: Hesla se neshodují. Bootstrap přerušen."
        exit 1
    fi

    echo "$VAULT_PASS" | sudo tee "$VAULT_PASS_FILE" >/dev/null
    sudo chmod 600 "$VAULT_PASS_FILE"
    unset VAULT_PASS VAULT_PASS_CONFIRM
    echo "Heslo úspěšně nastaveno."
fi

# Klonování/aktualizace repozitáře
if [ -d "$ANSIBLE_DIR/.git" ]; then
    echo "Aktualizuji existující repozitář..."
    sudo git -C "$ANSIBLE_DIR" reset --hard
    sudo git -C "$ANSIBLE_DIR" clean -fd
    sudo git -C "$ANSIBLE_DIR" pull --force
else
    echo "Klonuji nový repozitář..."
    sudo rm -rf "$ANSIBLE_DIR"/* 2>/dev/null || true
    sudo git clone https://github.com/janfai/ansible-config.git "$ANSIBLE_DIR"
fi

# Čištění při chybě
cleanup() {
    echo "Čištění po chybě..."
    sudo rm -rf "$VAULT_PASS_FILE" "$BOOTSTRAP_FLAG"
    exit 1
}
trap cleanup ERR

# Spuštění Ansible
sudo ansible-pull \
  -U https://github.com/janfai/ansible-config.git \
  -i inventories/vm-mint \
  --vault-password-file "$VAULT_PASS_FILE" \
  playbooks/vm-mint.yml

# Označení úspěšného dokončení
sudo touch "$BOOTSTRAP_FLAG"
echo "Bootstrap úspěšně dokončen. Pro opětovné spuštění odstraňte $BOOTSTRAP_FLAG"
