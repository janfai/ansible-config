# Správa stanic Linux Mint

Vydávání změn přes kanárkovou větev popisuje [postup stagingu](docs/staging.md).

Každá stanice každých 15 minut stáhne nakonfigurovanou větev pomocí systemd timeru a spustí `local.yml` jako root. Před spuštěním se ověří SSH podpis commitu proti `files/allowed_signers`. Identitu čte z `/etc/ansible/station-id`; proměnné stanice jsou v `host_vars/` a citlivé údaje v samostatném SOPS souboru.

## Založení stanice

Na čistém Linux Mintu stáhněte zaváděcí skript a spusťte jej jako root:

```bash
curl -fsSLo /tmp/bootstrap.sh https://raw.githubusercontent.com/janfai/ansible-config/main/bootstrap.sh
sudo bash /tmp/bootstrap.sh lada main
rm -f /tmp/bootstrap.sh
```

Druhý parametr bootstrapu určuje počáteční větev; při vynechání se použije `main`. Větev po instalaci určuje `ansible_pull_branch` v `host_vars/<id>.yml`.

Použitelná ID jsou `lada`, `milan`, `jitka`, `lucie`, `vlada`, `alan` a `vm-mint`. Skript nainstaluje potřebné balíčky, připne SOPS ke konkrétní verzi a kontrolnímu součtu, vytvoří klíč age a zapne časovač. Veřejný klíč age vypíše pro doplnění do `.sops.yaml`.

## Přidání stanice

1. Založte `host_vars/<id>.yml` pouze s neosobní konfigurací.
2. Na stanici spusťte `bootstrap.sh <id>` a přidejte vypsaný veřejný klíč do `.sops.yaml`.
3. Zašifrujte tajemství do `secrets/<id>.enc.yaml` přes `sops --encrypt --input-type yaml --output-type yaml`.
4. Ověřte lint a syntaxi, potom změnu začleňte do cílové větve.

Tajemství obsahují `SMTP_RELAY_HOST`, `SMTP_PASS_<ID>` a `USER_EMAIL`. SOPS soubory ani soukromé klíče se nikdy neukládají v nezašifrované podobě.

## Kontrola

```bash
yamllint $(git ls-files '*.yml' '*.yaml' ':!:secrets/*') .sops.yaml .yamllint
ansible-lint local.yml group_vars/ host_vars/ roles/
ansible-playbook --syntax-check local.yml
```

Architekturu a provozní poznámky popisuje [docs/architecture.md](docs/architecture.md) a [docs/troubleshooting.md](docs/troubleshooting.md).
