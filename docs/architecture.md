# Architektura

## Spuštění

`bootstrap.sh <id> [větev]` se spouští jednou ručně jako root na stanici Linux Mint. Nainstaluje Ansible, Git a age, ověří kontrolní součet připnutého SOPS, založí `/etc/ansible/station-id` a `/etc/ansible/age.key` a aktivuje `ansible-pull.timer`. Větev může být `main` nebo `next`; bez parametru se použije `main`. Timer spustí `ansible-pull` po startu a poté jednou denně; po vypnutí nebo spánku se zmeškaný běh provede po dalším startu.

Systemd služba čeká na `network-online.target` a volá `ansible-pull -U https://github.com/janfai/ansible-config.git -C <větev> -i localhost, local.yml`. Soukromý age klíč je dostupný pouze rootovi.

## Proměnné a tajemství

`local.yml` načte `group_vars/mint.yml`, `host_vars/<id>.yml` a pomocí `community.sops.sops` rozšifruje `secrets/<id>.enc.yaml`. Povolená ID jsou `lada`, `milan`, `jitka`, `lucie`, `vlada`, `alan` a `vm-mint`. Veřejné klíče stanic se po bootstrapu doplňují mezi příjemce v `.sops.yaml`; výchozí soubor obsahuje klíč NASu.

SOPS tajemství obsahují adresu relay serveru, heslo SMTP účtu a adresu uživatele. Konfigurační soubory, dokumentace i názvy stanic v Gitu používají pouze pseudonymy. Tajemství se nikdy nevypisují do protokolu Ansible.

## Role

- `common`: užitečné balíčky, české prostředí, bezpečnostní aktualizace bez automatického restartu, kontrola místa v `/boot` a dostupnosti Timeshiftu.
- `sops_client`: instalace připnutého SOPS s ověřeným SHA-256.
- `mail`: Postfix pouze pro odchozí poštu přes ověřený šifrovaný přenos; systémové adresy přepisuje na přihlašovací účet stanice.
- `smartd`: kontrola disků přes smartmontools.
- `reporting`: týdenní přehled, prahová upozornění a připomínky k aktualizacím.
- `inventory`: jednorázový inventář pouze pro stanici `lada`; jeho porovnávací seznam balíčků se doplní po pořízení čisté instalace Mint ve VM.

Příjemci alertů a úplné adresy serverů se doplní výhradně v šifrovaných souborech. Mailname zůstává do ověření poštovního serveru ve tvaru `<id>.stanice.invalid`.

## Zašifrování tajemství

Vytvořte dočasný YAML soubor mimo Git s poli `SMTP_RELAY_HOST`, `SMTP_ACCOUNT`, `SMTP_PASS_<ID>`, `USER_EMAIL`, `ADMIN_EMAIL` a `ADMIN_SIGNATURE`; zašifrujte jej příkazem `sops --encrypt --input-type yaml --output-type yaml <soubor>` a uložte výsledek jako `secrets/<id>.enc.yaml`. Soubor s otevřeným textem bezpečně odstraňte až po ověření šifrovaného výstupu. Klíče příjemců jsou age klíč NASu a klíč konkrétní stanice.

## Ověření

Před nasazením spusťte yamllint, ansible-lint a `ansible-playbook --syntax-check local.yml`. Příkazy měnící systém se ověřují až na testovací VM Linux Mint; role se nespouštějí na vývojovém počítači.
