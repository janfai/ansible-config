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

Codex se instaluje pouze pro provider `codex` z archivu oficiálního vydání OpenAI `rust-v0.164.0`. SHA256 archivu `codex-x86_64-unknown-linux-musl.tar.gz` se ověřuje proti GitHub release digestu `90dd0b03b28afcb7fa733a4f73b413db2916a47347efd43fb669cc1c774ee8e4`. Nainstalovaná binárka má SHA256 `b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306`. Přihlášení provádí samostatně orchestrátor.

## Kompatibilita a ověření E2E

`guardian_relay_legacy_auth: true` v konfiguraci stanice explicitně povoluje autentizaci proti starému relay bez staniční hlavičky. Výchozí hodnota je false; automatický downgrade se neprovádí. Pro vm-mint je dočasně zapnutý, protože relay na VPS ještě používá původní protokol. URL s tajným prefixem může být v šifrovaném staničním souboru jako `relay_url`.

Změna configu restartuje službu. Vendorovaný runtime obsahuje trvalý outbox a recovery upgrade-state. Také běžný `cmd` zapisuje stav před spuštěním a po restartu se označí jako přerušený; automaticky se neopakuje. Typ `upgrade` navíc uchovává dokončené kroky. Po restartu rozpracovaný upgrade vrátí `blocked_waiting_instructions`, neopakuje přerušený krok a neprovádí automatický rollback.

Role zatím neprovádí registraci staničního klíče do Hetzner Git mailboxu ani jeho klonování. Bez této samostatné přípravy je funkční pouze HTTPS relay; samotný adresář repo není funkční fallback. Nevydávat nasazení za úplné, dokud není ověřený Git origin, SSH klíč a připnutý host key mailboxu.
