# Staging a povýšení změn

Stanice používají `ansible_pull_branch` z `host_vars/<id>.yml`; pokud není nastaven, platí `main`. `vm-mint` (testovací `mint_test`) sleduje `staging`. Bootstrap nastaví počáteční větev a první úspěšný Ansible běh zapíše deklarovanou větev stanice do `/etc/ansible/ansible-pull.env` pro další ověřený pull. Při prvním zprovoznění kanárka nastavte počáteční větev `staging` také v bootstrapu; existující stanici je nutné jednorázově přepnout na `staging`, protože konfigurace z `main` nemůže sama načíst změnu, která zatím existuje jen ve `staging`.

V každém pracovním klonu nastavte SSH podepisování lokálně:

```bash
git config --local gpg.format ssh
git config --local user.signingkey "$(realpath ~/.ssh/id_ed25519.pub)"
git config --local commit.gpgsign true
git config --local gpg.ssh.allowedSignersFile files/allowed_signers
```

Stanice stahují přes `ANSIBLE_CONFIG_REPOSITORY` z `/etc/ansible/ansible-pull.env`. Bootstrap nastavuje výchozí repozitář na VPS (`fleet`); `origin` je GitHub pro druhou kopii. Promotování pouze na GitHub proto nestačí pro stanice.

## Postup vydání

1. Proveďte změnu, spusťte kontroly a commit podepište Janovým SSH podpisovým klíčem.
2. Pushněte změnu do větve `staging` na VPS (`fleet`); canary stanice tuto větev stahují.
3. Počkejte na úspěšný pull na `vm-mint` a ověřte výsledek na testovací stanici.
4. Fast-forwardněte `main` na ověřený commit ze `staging`.

Skript `bin/promote-staging` ověří, že lokální `staging` navazuje na `main`, všechny commity nad `main` mají platný SSH podpis a jsou nastavené oba remotes `fleet` (VPS) a `origin` (GitHub). Pro `--push` vyžaduje `VM_MINT_PULL_STATUS_FILE` i `VM_MINT_B_PULL_STATUS_FILE`; oba soubory musí obsahovat `success <sha>` pro přesný HEAD staging. Samotný skript na žádný stroj nepřistupuje.

Bez přepínače `--push` skript pouze provede kontroly. S `--push` nejprve aktualizuje `staging` na VPS i GitHubu, potom fast-forwardem aktualizuje `main` na obou remotes. Nepoužívá force push; pokud vzdálená větev není fast-forwardovatelná, push selže a skript nepřepisuje její historii.
