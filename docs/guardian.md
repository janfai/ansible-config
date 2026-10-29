# Guardian

## Vendorovaná runtime kopie

Runtime se přebírá z `~/Work/bin/guardian` a `~/Work/infra/guardian.service`. Při nové verzi zkopíruj runtime a jednotku do `roles/guardian/files/`, aktualizuj `VERSION` a přegeneruj `MANIFEST`:

```sh
cd roles/guardian/files && sha256sum guardian guardian.service VERSION > MANIFEST
```

Playbook ověřuje soubory podle manifestu před instalací.

## Zapnutí a šifrovaná tajemství

Příznak a veřejnou konfiguraci nastav pouze v `host_vars/<id>.yml`:

```yaml
guardian_enabled: true
guardian_provider: none
guardian_station_id: <id>
```

`none` je výchozí provider pro dočasné systémové úlohy, například upgrade. Role zachová službu, relay, mailbox a podepsané úlohy `cmd`, `upgrade`, `watch`, `ping` a `retire`; neinstaluje Codex, nevytváří účet `guardian-agent` a úlohy `agent` i `auth` vrací `no-agent`. Provider `codex` přidá Codex CLI a izolovaný účet/profil. Provider `claude` používá existující tokenovou cestu.

Vytvoř soubor YAML pouze v RAM nebo zabezpečeném dočasném úložišti s poli `hmac_key` a `allowed_signers`. HMAC hodnota má nejméně 32 znaků; `allowed_signers` obsahuje veřejný klíč OpenSSH s principalem `jan` a namespace `guardian`, což odpovídá výchozímu podpisovému ID Guardiana. Zašifruj do cílové cesty přes SOPS, aniž bys hodnoty vypisoval do terminálu nebo logu:

```sh
sops --filename-override host_vars/<id>.sops.yaml --encrypt --input-type yaml --output-type yaml /bezpecne/guardian-secrets.yaml > host_vars/<id>.sops.yaml
```

SOPS pravidlo v `.sops.yaml` používá existující age příjemce repozitáře. Při `guardian_enabled: false` role zastaví službu, odstraní runtime adresáře a dedikovaný účet; uživatelské domovské adresáře role nemaže.

## Codex CLI

Codex se instaluje pouze pro provider `codex` z archivu oficiálního vydání OpenAI `rust-v0.164.0`. SHA256 archivu `codex-x86_64-unknown-linux-musl.tar.gz` se ověřuje proti GitHub release digestu `90dd0b03b28afcb7fa733a4f73b413db2916a47347efd43fb669cc1c774ee8e4`. Nainstalovaná binárka má SHA256 `b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306`. Přihlášení provádí samostatně orchestrátor.

## Výjimka vm-linux

`host_vars/vm-linux.yml` výslovně nastavuje trvalý Guardian s camouflage a Codex providerem. `local.yml` předává `guardian_mode` a `guardian_camouflage` z host konfigurace; běžné stanice zůstávají na výchozím `temporary` a `false`. Test `test_regular_station_keeps_default_guardian_profile_and_vm_linux_is_explicit_exception` tuto hranici hlídá.

Padding Guardiana, lokální jitter časovačů workeru a VPN gate jsou provozní invarianty vm-linux. Role je nepřenáší do fleet defaults, nespravuje jejich drop-iny a nemaže je při správě Guardian služby. Jejich změna vyžaduje samostatné výslovné rozhodnutí; Ansible změny samy o sobě nejsou nasazením na vm-linux.

## Kompatibilita a ověření E2E

`guardian_relay_legacy_auth: true` v konfiguraci stanice explicitně povoluje autentizaci proti starému relay bez staniční hlavičky. Výchozí hodnota je false; automatický downgrade se neprovádí. Pro vm-mint je dočasně zapnutý, protože relay na VPS ještě používá původní protokol. URL s tajným prefixem může být v šifrovaném staničním souboru jako `relay_url`.

Změna configu restartuje službu. Vendorovaný runtime obsahuje trvalý outbox a recovery upgrade-state. Také běžný `cmd` zapisuje stav před spuštěním a po restartu se označí jako přerušený; automaticky se neopakuje. Typ `upgrade` navíc uchovává dokončené kroky. Po restartu rozpracovaný upgrade vrátí `blocked_waiting_instructions`, neopakuje přerušený krok a neprovádí automatický rollback.

`guardian_git_enabled: true` zapíná přípravu Git mailboxu. Role vygeneruje staniční Ed25519 klíč v `/etc/guardian/station_ed25519`; privátní část zůstává na stanici s právy 0600. Instaluje alias `guardian-git-vps` na `178.105.1.151:10022`, účet `guardian-git`, `IdentitiesOnly yes`, `StrictHostKeyChecking yes` a připnutý ED25519 host key s fingerprintem `SHA256:UB5t/EXvsOuIsJ5xISsRZQoBao7WxxIwr3UfKVoJ83E`.

Registraci provádí orchestrátor z Work příkazem `bin/guardian-git-enroll --id <id> --station <ssh-cíl> --master-key <veřejný-klíč> --dry-run`; po kontrole zopakuje bez `--dry-run`. Nástroj čte pouze veřejný staniční klíč, kontroluje existující účet, AllowUsers a přesný obsah gate, zamyká registraci, před změnou zálohuje authorized_keys a přidává staniční i master klíč s `restrict` a forced commandem pro jediné repo. Založí a osadí prázdné bare repo, existující historii zachová. SSH daemon nemění ani nereloaduje. Vyžaduje předem připravený účet a gate dle T8. Pro stanice mimo fleet slouží `guardian-ctl deploy`; spravované stanice používají tuto roli a nový enroll.

První pull před registrací bezpečně skončí na fetchi; klíč už je připravený pro enroll. Po registraci spusťte `sudo systemctl start ansible-pull`. Role inicializuje repo i v původním neprázdném adresáři a zachová lokální výsledky. Dokončení označí souborem `.git/guardian-initialized`; další pull historii nepřepisuje. `tests/test_guardian_mailbox.py` ověřuje předání příznaku, fingerprint a skutečný Git roundtrip se zachováním offline výsledku v izolovaných dočasných repozitářích.
