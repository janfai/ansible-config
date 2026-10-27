# Řešení potíží

## Stanice nespouští správu

Ověřte `/etc/ansible/station-id`, stav `ansible-pull.timer` a poslední výsledek služby `ansible-pull.service`. Služba čeká na připojení k síti. Ruční spuštění lze provést přes `systemctl start ansible-pull.service`.

## Git clone nebo pull odmítá spojení

Ověřte, že `/etc/ansible/git_ed25519` existuje s režimem `0600`, veřejný klíč stanice je zaregistrován přes `fleet-enroll` a `/etc/ansible/known_hosts` obsahuje správný záznam pro port 10022. Fingerprint ověřte proti nezávisle předané hodnotě; nevypínejte `StrictHostKeyChecking`.

## Nelze rozšifrovat tajemství

Ověřte, že `secrets/<id>.enc.yaml` obsahuje veřejný klíč této stanice a že soukromý klíč `/etc/ansible/age.key` existuje a má režim `0600`. Veřejný klíč lze znovu zobrazit příkazem `age-keygen -y /etc/ansible/age.key`.

## Pošta se nedoručuje

Zkontrolujte stav Postfixu a jeho frontu. Heslo musí odpovídat SMTP účtu stanice uloženému v SOPS. Ověření serverového názvu, certifikátu a `mailname` se musí provést proti testovacímu serveru před nasazením.

## Nedostatek místa

Přehled každé stanice obsahuje zaplnění `/`, `/boot` a `/home`. Upozornění se spustí při zaplnění `/` nebo `/boot` nad 90 procent. Odstranění souborů či snímků systému se neprovádí automaticky.
