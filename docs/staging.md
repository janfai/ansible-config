# Staging a povýšení změn

Stanice používají `ansible_pull_branch` z `host_vars/<id>.yml`; pokud není nastaven, platí `main`. `vm-mint` (testovací `mint_test`) sleduje `staging`. Bootstrap nastaví počáteční větev a první úspěšný Ansible běh zapíše deklarovanou větev stanice do `/etc/ansible/ansible-pull.env` pro další ověřený pull.

## Postup vydání

1. Proveďte změnu, spusťte kontroly a commit podepište Janovým SSH podpisovým klíčem.
2. Pushněte změnu do větve `staging`.
3. Počkejte na úspěšný pull na `vm-mint` a ověřte výsledek na testovací stanici.
4. Fast-forwardněte `main` na ověřený commit ze `staging`.

Skript `bin/promote-staging` ověří, že lokální `staging` navazuje na `main` a jeho HEAD má platný SSH podpis. Pokud je nastaven `VM_MINT_PULL_STATUS_FILE` a soubor existuje, očekává v něm `success <sha>` pro přesný HEAD. Bez dostupného stavového souboru vyžaduje pouze podpis. Samotný skript na žádný stroj nepřistupuje.

Bez přepínače `--push` skript pouze provede kontroly. S `--push` nejprve pushne `staging` a potom provede fast-forward push `staging` do `main`; nepoužívá force push.
