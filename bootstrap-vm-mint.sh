#!/bin/bash
set -euo pipefail

ANSIBLE_DIR="/var/lib/ansible"
VAULT_PASS_FILE="/etc/ansible/.vault_pass"  # Změna cesty
BOOTSTRAP_FLAG="/etc/ansible/bootstrap_completed"

# Kontrola dokončení
if [ -f "$BOOTSTRAP_FLAG" ]; then
    echo "Bootstrap již byl proveden. Pro opětovné spuštění odstraňte $BOOTSTRAP_FLAG"
    exit 0
fi

# Instalace závislostí a nastavení adresářů
sudo apt update && sudo apt install -y git ansible
sudo mkdir -p "$ANSIBLE_DIR" "/etc/ansible"
sudo chmod 750 "$ANSIBLE_DIR"
sudo chown -R root:root "$ANSIBLE_DIR" "/etc/ansible"

# Zadání a ověření hesla
if [ ! -f "$VAULT_PASS_FILE" ]; then
    echo "Zadejte heslo pro Ansible Vault:"
    read -s -r VAULT_PASS
    echo "Zadejte heslo znovu pro ověření:"
    read -s -r VAULT_PASS_CONFIRM

    if [ "$VAULT_PASS" != "$VAULT_PASS_CONFIRM" ]; then
        echo "Chyba: Hesla se neshodují!"
        exit 1
    fi

    echo "$VAULT_PASS" | sudo tee "$VAULT_PASS_FILE" >/dev/null
    sudo chmod 600 "$VAULT_PASS_FILE"
    unset VAULT_PASS VAULT_PASS_CONFIRM
fi

# Klonování/aktualizace repozitáře
if [ -d "$ANSIBLE_DIR/.git" ]; then
    sudo git -C "$ANSIBLE_DIR" pull --force
else
    sudo git clone https://github.com/janfai/ansible-config.git "$ANSIBLE_DIR"
fi

# Spuštění Ansible
#!/bin/bash
set -euo pipefail

ANSIBLE_DIR="/var/lib/ansible"
VAULT_PASS_FILE="/etc/ansible/.vault_pass"
BOOTSTRAP_FLAG="/etc/ansible/bootstrap_completed"

if [ -f "$BOOTSTRAP_FLAG" ]; then
    echo "Bootstrap již byl proveden. Pro opětovné spuštění odstraňte $BOOTSTRAP_FLAG"
    exit 0
fi

sudo apt update && sudo apt install -y git ansible
sudo mkdir -p "$ANSIBLE_DIR" "/etc/ansible"
sudo chmod 750 "$ANSIBLE_DIR"
sudo chown -R root:root "$ANSIBLE_DIR" "/etc/ansible"

if [ ! -f "$VAULT_PASS_FILE" ]; then
    echo "Zadejte heslo pro Ansible Vault:"
    read -s -r VAULT_PASS
    echo "Zadejte heslo znovu pro ověření:"
    read -s -r VAULT_PASS_CONFIRM

    if [ "$VAULT_PASS" != "$VAULT_PASS_CONFIRM" ]; then
        echo "Chyba: Hesla se neshodují!"
        exit 1
    fi

    echo "$VAULT_PASS" | sudo tee "$VAULT_PASS_FILE" >/dev/null
    sudo chmod 600 "$VAULT_PASS_FILE"
    unset VAULT_PASS VAULT_PASS_CONFIRM
fi

if [ -d "$ANSIBLE_DIR/.git" ]; then
    sudo git -C "$ANSIBLE_DIR" pull --force
else
    sudo git clone https://github.com/janfai/ansible-config.git "$ANSIBLE_DIR"
fi

sudo ansible-pull \
  -U https://github.com/janfai/ansible-config.git \
  -d "$ANSIBLE_DIR" \
  -i inventories/vm-mint \
  --vault-password-file "$VAULT_PASS_FILE" \
  playbooks/vm-mint.yml

# Označení úspěchu
sudo touch "$BOOTSTRAP_FLAG"
echo "Bootstrap úspěšně dokončen!"
