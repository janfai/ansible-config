# Ansible Pull konfigurace pro správu stanic a serverů

Spusťte universal-bootstrap.sh na cílovém serveru nebo stanici:
```
curl -O https://raw.githubusercontent.com/janfai/ansible-config/main/universal-bootstrap.sh && chmod +x universal-bootstrap.sh
```

## Použití:
### Pro VM-Mint
```bash
sudo ./universal-bootstrap.sh -i inventories/vm-mint -p playbooks/vm-mint.yml
```
### Pro Debian stanici
```bash
sudo ./universal-bootstrap.sh -i inventories/debian-desktop -p playbooks/workstation.yml
```
### Pro server
```bash
sudo ./universal-bootstrap.sh -i inventories/production-server -p playbooks/server.yml
```

## Výhody tohoto řešení:
1. **Univerzálnost**: Jediný skript pro všechny typy zařízení
2. **Parametrizace**: Možnost specifikovat inventory a playbook
3. **Bezpečnost**: Heslo Vaultu se nikde neukládá v plaintextu
4. **Idempotence**: Lze spouštět opakovaně bez vedlejších účinků
5. **Integrace s cronem**: Můžete přidat cron úlohu pro pravidelnou aktualizaci

## Doporučené vylepšení:
Pro automatizované nasazení na více zařízení můžete vytvořit wrapper skript, který bude spouštět tento univerzální bootstrap s různými parametry.
