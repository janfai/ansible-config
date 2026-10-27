# Staging a povýšení změn

Stanice používají `ansible_pull_branch` z `host_vars/<id>.yml`; pokud není nastaven, platí `main`. `vm-mint` (testovací `mint_test`) sleduje `staging`. Bootstrap nastaví počáteční větev a první úspěšný Ansible běh zapíše deklarovanou větev stanice do `/etc/ansible/ansible-pull.env` pro další ověřený pull. Při prvním zprovoznění kanárka nastavte počáteční větev `staging` také v bootstrapu; existující stanici je nutné jednorázově přepnout na `staging`, protože konfigurace z `main` nemůže sama načíst změnu, která zatím existuje jen ve `staging`.

V každém pracovním klonu nastavte SSH podepisování lokálně:

```bash
git config --local gpg.format ssh
git config --local user.signingkey "$(realpath ~/.ssh/id_ed25519.pub)"
git config --local commit.gpgsign true
git config --local gpg.ssh.allowedSignersFile files/allowed_signers
```

## Postup vydání

1. Proveďte změnu, spusťte kontroly a commit podepište Janovým SSH podpisovým klíčem.
2. Pushněte změnu do větve `staging`.
3. Počkejte na úspěšný pull na `vm-mint` a ověřte výsledek na testovací stanici.
4. Fast-forwardněte `main` na ověřený commit ze `staging`.

Skript `bin/promote-staging` ověří, že lokální `staging` navazuje na `main` a jeho HEAD má platný SSH podpis. Pokud je nastaven `VM_MINT_PULL_STATUS_FILE` a soubor existuje, očekává v něm `success <sha>` pro přesný HEAD. Bez dostupného stavového souboru vyžaduje pouze podpis. Samotný skript na žádný stroj nepřistupuje.

Bez přepínače `--push` skript pouze provede kontroly. S `--push` nejprve pushne `staging` a potom provede fast-forward push `staging` do `main`; nepoužívá force push.
