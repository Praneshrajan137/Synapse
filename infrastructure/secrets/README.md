# SYNAPSE Secrets — SOPS + age pattern (Sprint 9 §M-sec-7, ADR-033 sibling)

Sprint 9 ships the **pattern** for encrypted secrets, not the actual
encrypted payloads. Each deployment org generates its own age key(s)
and registers them in [`.sops.yaml`](.sops.yaml).

## One-time setup (per environment)

1. Install [`sops`](https://github.com/getsops/sops) and
   [`age`](https://github.com/FiloSottile/age).
2. Generate an age keypair:
   ```bash
   mkdir -p ~/.config/sops/age
   age-keygen -o ~/.config/sops/age/keys.txt
   ```
3. Copy the **public** key (line starting `age1…`) into
   `.sops.yaml` under the matching `creation_rules` block. Commit
   `.sops.yaml`. **Never commit the private key.**
4. Export the private-key file path so sops can find it:
   ```bash
   export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
   ```

## Daily flow

- **Edit a secret** (decrypts on the fly):
  ```bash
  sops infrastructure/secrets/dev.local.yaml
  ```
- **Encrypt a fresh file**:
  ```bash
  cp dev.example.yaml dev.local.yaml
  # fill in values
  sops --encrypt --in-place dev.local.yaml
  ```
- **Decrypt for use** (e.g. into env vars at startup):
  ```bash
  sops --decrypt dev.local.yaml | yq -r 'to_entries | .[] | "\(.key)=\(.value)"' >> .env
  ```

## CI integration

The `cd.yml` workflow already pulls `GITHUB_TOKEN` for the audit-anchor
upload. For secrets injection in production deployments:

1. Generate a CI-specific age keypair.
2. Store the private key as a GitHub Actions secret named `SOPS_AGE_KEY`.
3. Add a decryption step:
   ```yaml
   - run: echo "${{ secrets.SOPS_AGE_KEY }}" > /tmp/sops-age.txt
   - env:
       SOPS_AGE_KEY_FILE: /tmp/sops-age.txt
     run: sops --decrypt infrastructure/secrets/prod.app.yaml > prod.env
   ```

## Key rotation runbook (quarterly)

1. Generate a new age keypair (`age-keygen -o new-keys.txt`).
2. Update `.sops.yaml` to list **both** the old and new public keys.
3. Re-encrypt every file with the new key:
   ```bash
   for f in infrastructure/secrets/*.yaml; do
     sops updatekeys "$f"
   done
   ```
4. After a one-sprint cooldown, drop the old public key from
   `.sops.yaml` and re-run the `updatekeys` loop.
5. Rotate the GitHub Actions `SOPS_AGE_KEY` secret last so CI keeps
   working through the cutover.

## What this ships vs what's deferred to your org

| Item | Sprint 9 ships | Your org adds |
|---|---|---|
| `.sops.yaml` template | ✅ | real age public keys |
| `dev.example.yaml` shape | ✅ | encrypted dev/staging/prod variants |
| `make secrets-encrypt` / `secrets-decrypt` | ✅ | nothing |
| Rotation runbook | ✅ | quarterly cron / calendar reminder |
| Production secret injection | seam in `cd.yml` | the GH Actions secret |
