# Dočasný Guardian

## Vendorovaná runtime kopie

Runtime se přebírá z `~/Work/.worktrees/guardian-codex/bin/guardian` a `infra/upgrade-guardian.service` ve větvi `codex/guardian-codex`. Při nové verzi zkopíruj oba soubory do `roles/guardian/files/`, aktualizuj `VERSION` a přegeneruj `MANIFEST`:

```sh
cd roles/guardian/files && sha256sum guardian upgrade-guardian.service VERSION > MANIFEST
```

Playbook ověřuje soubory podle manifestu před instalací.

## Zapnutí a šifrovaná tajemství

Příznak a veřejnou konfiguraci nastav pouze v `host_vars/<id>.yml`:

```yaml
guardian_enabled: true
guardian_provider: codex
guardian_station_id: <id>
guardian_relay_url: https://<relay>/guardian
```

Vytvoř soubor YAML pouze v RAM nebo zabezpečeném dočasném úložišti s poli `hmac_key` a `allowed_signers`. HMAC hodnota má nejméně 32 znaků; `allowed_signers` obsahuje veřejný klíč OpenSSH s principalem `jan` a namespace `upgrade-guardian`, což odpovídá výchozímu podpisovému ID Guardiana. Zašifruj do cílové cesty přes SOPS, aniž bys hodnoty vypisoval do terminálu nebo logu:

```sh
sops --filename-override host_vars/<id>.sops.yaml --encrypt --input-type yaml --output-type yaml /bezpecne/guardian-secrets.yaml > host_vars/<id>.sops.yaml
```

SOPS pravidlo v `.sops.yaml` používá existující age příjemce repozitáře. Při `guardian_enabled: false` role zastaví službu, odstraní runtime adresáře a dedikovaný účet; uživatelské domovské adresáře role nemaže.

## Codex CLI

Codex se instaluje pouze pro provider `codex`, pouze pokud jeho binárka chybí, oficiálním instalátorem OpenAI s připnutou verzí `0.164.0`. Paměťový report k `mint_test` nedoložil SHA256 instalačního skriptu ani vydané binárky.
