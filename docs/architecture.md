# Architektura

## Spuštění

`bootstrap.sh <id> [větev] SHA256:<fingerprint>` se spouští jednou ručně jako root na stanici Linux Mint. Nainstaluje Ansible, Git a age, ověří kontrolní součet připnutého SOPS, založí `/etc/ansible/station-id` a `/etc/ansible/age.key`, vygeneruje `/etc/ansible/git_ed25519` a aktivuje `ansible-pull.timer`. Větev je při vynechání `main`; repozitář lze přepsat proměnnou `ANSIBLE_CONFIG_REPOSITORY`. Bootstrap stáhne host key `vps.faix.cz:10022`, ověří jej proti předanému SHA-256 fingerprintu a uloží do `/etc/ansible/known_hosts`.

První clone i systemd služba používají stejné `GIT_SSH_COMMAND` s deploy klíčem, `known_hosts` a `StrictHostKeyChecking=yes`. `/etc/ansible/ansible-pull.env` určuje URL repozitáře a větev. Timer spouští pull po 3 minutách od startu a následně každých 15 minut, s náhodným posunem do 2 minut a persistentním během po výpadku. Selhání služby zpracovává `ansible-pull-failure.service`. Soukromé age i Git klíče jsou dostupné pouze rootovi.

## Proměnné a tajemství

`local.yml` načte `group_vars/mint.yml`, `host_vars/<id>.yml` a pomocí `community.sops.sops` rozšifruje `secrets/<id>.enc.yaml`. Povolená ID jsou `lada`, `milan`, `jitka`, `lucie`, `vlada`, `alan` a `vm-mint` (testovací stanice `mint_test`). Veřejné age klíče stanic se po bootstrapu doplňují mezi příjemce v `.sops.yaml`; veřejné Git klíče se předávají správci VPS a registrují přes `fleet-enroll <id> <pubkey-file>`.

SOPS tajemství obsahují adresu relay serveru, heslo SMTP účtu a adresu uživatele. Konfigurační soubory, dokumentace i názvy stanic v Gitu používají pouze pseudonymy. Tajemství se nikdy nevypisují do protokolu Ansible.

## Role

- `base_tools`: **Janův standardní seznam CLI nástrojů pro všechny stanice a servery** (mc, htop, btop, atop, iotop, iftop, iptraf-ng, nmap, vim, ncdu, smartmontools, needrestart…, proměnná `base_tools_packages`, per-stanice rozšíření `base_tools_extra_packages`, vypnutí `base_tools_enabled: false`). Než sem přidávat další standardní/běžné nástroje jinou cestou, zkontroluj tuto roli a `~/Work/memory/preferences/standard-cli-tools.md` (zdroj a odůvodnění seznamu) — ať nevznikne duplicitní/konfliktní role se stejným účelem.
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
