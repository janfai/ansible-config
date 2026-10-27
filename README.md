# Správa stanic Linux Mint

Každá stanice každých 15 minut zkusí stáhnout nakonfigurovanou větev pomocí systemd timeru a spustí `local.yml` jako root. Identitu čte z `/etc/ansible/station-id`; proměnné stanice jsou v `host_vars/` a citlivé údaje v samostatném SOPS souboru. Git přístup je přes samostatný SSH klíč stanice, který smí pouze číst repozitář.

## Založení stanice

Připravte změny pro stanici v tomto repozitáři, zejména `host_vars/<id>.yml`, `secrets/<id>.enc.yaml` a příjemce v `.sops.yaml`; začleňte je do větve, kterou bude stanice číst. Na stanici bezpečně přeneste `bootstrap.sh` a ověřený SHA-256 fingerprint SSH host key `vps.faix.cz:10022` (předávaný správcem mimo toto spojení). Bootstrap se získává z důvěryhodného přenosu, protože stanice ještě nemá zaregistrovaný Git klíč.

Spusťte bootstrap jako root:

```bash
sudo bash ./bootstrap.sh lada main SHA256:<ověřený-fingerprint>
```

První parametr je pevné ID stanice. Větev se zadává jako druhý parametr a při vynechání se použije `main`; fingerprint `SHA256:...` je povinný poslední parametr (při výchozí větvi tedy druhý). Bootstrap stáhne host key na portu 10022, ověří fingerprint a zapíše jej do `/etc/ansible/known_hosts`; SSH vyžaduje striktní kontrolu host key. URL lze přepsat proměnnou `ANSIBLE_CONFIG_REPOSITORY`, jejíž výchozí hodnota je `ssh://fleet-config@vps.faix.cz:10022/srv/fleet-config/ansible-config.git`.

Použitelná ID jsou `lada`, `milan`, `jitka`, `lucie`, `vlada`, `alan` a `vm-mint` (testovací stanice `mint_test`). Skript nainstaluje potřebné balíčky, připne SOPS ke konkrétní verzi a kontrolnímu součtu, vytvoří klíč age a bez hesla deploy SSH klíč `/etc/ansible/git_ed25519` s režimem `0600`; zapne časovač. Na konci vypíše age i SSH veřejný klíč.

## Přidání stanice

1. Přidejte ID do allowlistu `group_vars/mint.yml`, založte `host_vars/<id>.yml` pouze s neosobní konfigurací a připravte šifrovaný soubor tajemství.
2. Zabezpečeným kanálem přeneste bootstrap na stanici a předejte jí ověřený fingerprint host key VPS.
3. Spusťte `bootstrap.sh <id> [větev] SHA256:<otisk>`. Bootstrap vytvoří age a Git klíč, ověří a připne host key, provede první clone a vypíše oba veřejné klíče.
4. Veřejný Git klíč zaregistrujte na VPS jako root přes `fleet-enroll <id> <pubkey-file>`; po registraci může stanice stáhnout repozitář přes SSH.
5. Přidejte age veřejný klíč do `.sops.yaml`, zašifrujte tajemství do `secrets/<id>.enc.yaml` přes `sops --encrypt --input-type yaml --output-type yaml` a začleňte změny do větve.
6. Ověřte lint a syntaxi. Na stanici probíhá pravidelný pull každých 15 minut.

Tajemství obsahují `SMTP_RELAY_HOST`, `SMTP_PASS_<ID>` a `USER_EMAIL`. SOPS soubory ani soukromé klíče se nikdy neukládají v nezašifrované podobě.

## Kontrola

```bash
yamllint $(git ls-files '*.yml' '*.yaml' ':!:secrets/*') .sops.yaml .yamllint
ansible-lint local.yml group_vars/ host_vars/ roles/
ansible-playbook --syntax-check local.yml
```

Architekturu a provozní poznámky popisuje [docs/architecture.md](docs/architecture.md) a [docs/troubleshooting.md](docs/troubleshooting.md).
