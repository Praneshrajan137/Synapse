# ADR-057: Access modes — open preview now, authenticated login dormant until activation

## Status
Accepted (2026-10-24) for D1–D6. The activation plan (D7) is a design, not an implementation:
nothing in it ships until its checklist is complete and a reviewed change flips the mode.

## Context

**Finding 89** (`.kiro/specs/decision-quality-proof/tasks.md`). The Sprint-16 boot hook
`frontend/src/surfaces/auth/useBootAutoLogin.ts` signed every visitor in as `admin`, falling
back to a development password compiled into the bundle, which matched a plaintext operator
table hardcoded in `api/routers/auth.py`. The repository has been public since 2026-10-02, so
that credential was readable in source and shipped in every production bundle: any deployment
of this tree signed anonymous visitors in as admin.

Reading the routes for this ADR found a second hole of the same class. `nginx.gcp.conf`
proxied `location /orchestrator/` on public 443, which put three anonymous orchestrator writes
on the internet — `POST /api/v1/hitl/{id}/resolve` (whose docstring claimed it was reachable
only on the internal network), `POST /api/v1/decisions`, and `POST /a2a` — and the gateway's
`POST /api/v1/orders/` took no token at all. `WS /ws/escalation` also accepted human responses
from any connection, skipping the gateway's audit-row-first override (FE-INV-021).

**The operator's directive (2026-10-15):** find the best login for this product and build it,
but keep it dormant: until the operator activates it after the product is finished, the console
must open without login.

### Threat model: the repository is public

Everything in the repository, the compose files and the frontend bundle is public. So a
secret may live only in server-side configuration the repository never holds (Secret
Manager, an env file on the VM), and every protection must hold against an adversary who has
read all of the code. Concretely:

- **Anything in the bundle is public.** No `VITE_` variable may hold a credential; a
  bundle-side "auto-login" is, by construction, a public password.
- **Anything in a compose file is public.** The access posture is visible, which is fine: it
  is a policy, not a secret. A secret default in compose (`${X:-default}`) is a published
  credential whenever the operator forgets to override it; *Adjacent exposures* below lists
  the ones found.
- **The public edge is nginx on 80/443.** The GCP firewall (`infrastructure/gcp/terraform/
  main.tf`, read, not probed live) opens only 80/443 to the world, and the management ports,
  the orchestrator's host port 8090 among them, only to the IAP range (or to `admin_ip_cidr`
  when `use_iap_only` is false). The edge config is therefore the boundary that decides which
  services the internet reaches.
- **Assets.** In open mode a visitor reads what a VIEWER reads: the console, the audit trail of
  simulated and autonomous decisions, posture. The writes — orders, steering, overrides, HITL
  resolution, decision triggers, A2A — are what an adversary must not reach.

## Decision

**D1 — Two settings, resolved at startup.** `SYNAPSE_ACCESS_MODE` is `open` (default) or
`authenticated`. `SYNAPSE_OPEN_AUTHORITY` is `view` (default, least privilege) or `act`, read
only in open mode. Any other value — an empty one included — refuses startup with a message
naming the variable (`api/access.py`; the gateway resolves both at import in `api/main.py`,
the orchestrator in its lifespan). `docker-compose.gcp.yml` sets `open` + `view` as literals on
the gateway and the orchestrator, so changing the public posture is a reviewed commit, never an
edit on the VM. The local `docker-compose.yml` sets `open` + `act` on its orchestrator, the only
backend service that stack runs behind nginx; D5 says what `act` admits there.

**D2 — Open mode: a preview grant, and sign-in dormant.** `POST /api/v1/auth/preview` (public)
issues a one-hour access token for the synthetic operator `preview`, signed by the same RS256
path, issuer and audience as a sign-in token, with one extra claim, `"preview": true`. Its role
is VIEWER (`view`) or OPS (`act`); signing refuses ENGINEER and above, and the operator store
refuses the id `preview`. It carries no refresh token: the console takes a fresh grant before
it lapses. `GET /api/v1/auth/mode` (public) returns `{mode, authority}`. `/auth/login` and
`/auth/refresh` answer 404 saying sign-in is not activated.

**D3 — Authenticated mode, built and dormant.** `/auth/preview` is a 404. `/auth/login`
verifies against `SYNAPSE_OPERATORS_JSON`, a list of
`{id, role, scrypt: {salt_b64, n, r, p, dklen, hash_b64}}`, using the standard library's
`hashlib.scrypt` and `hmac.compare_digest` (`api/operators.py`). The
[OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
(accessed 2026-10-24) puts Argon2id first and scrypt next, for when Argon2id is not available;
the standard library has no Argon2id and this ADR adds no dependency, so the store uses scrypt.
Its cost floor is the code's rule: `N` a power of two of at least 2^13, `r` of at least 8 and
`N·p` of at least 81,920, under a per-derivation memory ceiling. That admits each of OWASP's
five scrypt rows (N=2^17 with p=1 down to N=2^13 with p=10, all with r=8) and refuses each row
with one less unit of `p`. Passwords are NFC-normalised before derivation, as
[NIST SP 800-63B-4 §3.1.1.2](https://pages.nist.gov/800-63-4/sp800-63b.html) recommends; an
unknown id still pays one derivation, so response time does not reveal which ids exist
([ASVS v5.0.0-6.3.8](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x15-V6-Authentication.md)).
A malformed store refuses startup **in either mode**, so it is found while still dormant, and the
refusal never echoes a salt or hash. `python -m api.operator_hash --id … --role …` builds an
entry: it reads the password twice with `getpass`, refuses one shorter than NIST's 15-character
single-factor floor or on the documented context-specific blocklist (ASVS v5.0.0-6.1.2 and
v5.0.0-6.2.11), and writes the entry only after the store has parsed it. The old plaintext table
survives only behind `SYNAPSE_DEV_OPERATORS_INSECURE=1`, logs a structured warning when enabled
and when consulted, is set in no compose file (a test pins that), and still cannot wake sign-in
in open mode. ASVS v5.0.0-6.3.2 asks that default accounts such as `admin` be absent or
disabled. Here they are disabled only while that opt-in is unset: in authenticated mode it
enables `admin@synapse.local` with a published password, so activation checklist item 6 proves
the opt-in absent on the VM.

**D4 — Verification follows the posture.** `api.middleware.jwt.verify_access_token`, used by
every gateway dependency and the firehose, honours a preview grant only while the gateway runs
open and only up to the current authority's role, re-read per request. Activating authenticated
mode therefore retires every outstanding grant at once, and lowering `act` to `view` caps the OPS
grants already issued — the revocation that self-contained tokens otherwise lack
([ASVS v5.0.0-7.4.1](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x16-V7-Session-Management.md)).

**D5 — The anonymous writes are closed.**

| Route | Legitimate callers (read) | Now |
|---|---|---|
| gateway `POST /api/v1/orders/` | console Ingress (ops) | `RequireRole(OPS)` |
| orch. `POST /api/v1/hitl/{id}/resolve` | the gateway's override, after its audit row | internal-only in every posture |
| orch. `POST /a2a` | none found (the orchestrator calls agents' `/a2a`, not its own) | internal-only in every posture |
| orch. `POST /api/v1/decisions` | traffic generator, deploy probe (`verify_live.py`), gateway OPS route, demo scripts — all on the compose network or the host; the local console's Ingress via nginx `/api/`, which stays closed because the local stack has no gateway to issue it a grant | internal-only, except an edge call in `open` + `act` |
| orch. `WS /ws/escalation` inbound | none (the console listens and sends heartbeats) | an edge connection is listen-only |

"Internal-only" is two locks: `nginx.gcp.conf` and `nginx.conf` deny `/orchestrator/` (and the
local edge denies `/api/v1/hitl/`), and `orchestrator/inference/serve.py` refuses a write that
carries a header nginx adds when it forwards (`X-Real-IP`, `X-Forwarded-For`, `Forwarded`,
`X-Forwarded-Proto`, `X-Forwarded-Host`). JWT verification was rejected for the orchestrator: it
holds none of the gateway's keys, which are ephemeral per process today. A `view` grant gets 403
on every gateway mutation; an `act` grant is accepted wherever OPS is.

**D6 — The console.** `VITE_AUTO_LOGIN*` and every bundled credential are gone. The boot hook
(file name kept so `providers.tsx` is untouched) reads `GET /auth/mode`: `open` takes a preview
grant and stores it exactly as a sign-in token; `authenticated` takes nothing and `RouteGuard`
sends the visitor to `/login`; an unreachable gateway still opens the console, whose surfaces
show their honest unavailable states. It re-attempts when the session falls back to anonymous, at
most once per 30 s. Every guarded surface carries a persistent badge, "Preview access - view only"
or "Preview access - can act". A route above the session's role renders an insufficient-authority
state that says why, never a `/login` redirect. `/login` in open mode says sign-in is not
activated. `router.tsx` and `Shell.tsx` are untouched (they conflict with PR #84): the badge and
the state render from `RouteGuard`.

### D7 — The activation plan (design only, not implemented)

The research question was which login fits a single-tenant operator console whose every
authority action already writes an append-only audit row. The answer is passkeys first, with
proof of presence bound to each authority action.

**Primary: passkeys.** [W3C Web Authentication Level 3](https://www.w3.org/TR/webauthn-3/),
a W3C Recommendation since [25 August 2026](https://www.w3.org/news/2026/web-authentication-an-api-for-accessing-public-key-credentials-level-3-is-now-a-w3c-recommendation/),
with discoverable credentials (`residentKey: "required"`), so sign-in needs no username and the
relying party need not identify the operator before the ceremony, and `userVerification:
"required"`, rejecting any assertion whose UV flag is clear. Phishing resistance is the reason:
[NIST requires an AAL2 verifier to offer at least one phishing-resistant option](https://pages.nist.gov/800-63-4/sp800-63b/aal/).
Syncable passkeys are acceptable: [NIST SP 800-63B-4 Appendix B](https://pages.nist.gov/800-63-4/sp800-63b/syncable/)
allows them at AAL2 under its sync-fabric conditions and rules them out only at AAL3, because
syncing makes the key exportable. ASVS draws the same line: its
[V6.3](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x15-V6-Authentication.md) expects
hardware-based authenticators, such as device-bound passkeys, only at level 3, so syncable ones
fit level 2. Store each credential's backup-eligible and backup-state flags at registration
(Appendix B lets a verifier restrict on the backup-eligible flag), so a policy can later demand
device-bound keys for ADMIN.

**Step-up for authority actions** (override, steering, HITL resolution), per
[ASVS v5.0.0-7.5.3](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x16-V7-Session-Management.md)'s
call for further verification before highly sensitive operations. The gateway canonicalises the
action payload (`json.dumps(sort_keys=True, separators=(",", ":"))`), hashes it with SHA-256, and
issues a single-use challenge: at least 16 random bytes generated server-side, followed by that
digest, held server-side until the ceremony ends. [WebAuthn §13.4.3](https://www.w3.org/TR/webauthn-3/)
requires (MUST) that the relying party generate the challenge randomly in an environment it
trusts, that the returned value match it, and that it carry enough entropy to make guessing
infeasible; a length of at least 16 bytes and holding the challenge server-side until the
operation completes are its SHOULDs, and this design adopts both. Appending the digest is this
design's own choice: it puts the action inside what the authenticator signs. The action request
carries the fresh assertion; the gateway re-derives the digest from the submitted payload,
verifies challenge, signature and UV, consumes the challenge, and records a **signed presence
attestation**: operator token ref, a reference to the `operator_credentials` row whose public key
verifies it, action kind, action digest, the raw `authenticatorData` and `clientDataJSON`, the
signature, and the gateway's own RS256 signature over the canonical row. The raw bytes are kept
because WebAuthn §7.2 checks the signature over `authenticatorData` concatenated with the
SHA-256 of `clientDataJSON`, so a row holding only their hashes could never be re-verified. The
row goes in a **new append-only table**, `operator_presence_attestations` (INSERT-only grant to
the app role). The audit row references it by id inside the JSON it already inserts (for
overrides, `audit_escalations.human_action`); steering's fixed-column table gains a nullable
reference column in an additive migration. **I-4 holds:** no audit row is ever UPDATEd or
DELETEd, and `make_canonical_row` is not touched; if the attestation table is chained, it gets
its own canonicaliser.

**Fallback: scrypt passwords**, exactly D3's store, for an operator without a passkey-capable
device. NIST's single-factor rules apply: at least 15 characters, a blocklist and rate limiting.
A password alone is one factor and [AAL2 needs two](https://pages.nist.gov/800-63-4/sp800-63b/aal/),
so password sign-in is AAL1; [ASVS v5.0.0-6.3.3](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x15-V6-Authentication.md)
asks a level-2 application for multi-factor authentication, or a combination of single-factor
mechanisms, and a documented rationale for any relaxation. The rationale, recorded here: a
password session can read and navigate, but it never satisfies step-up, so every authority
action still needs a passkey assertion. **Decision (blocklist):** NIST §3.1.1.2 requires the
blocklist to hold commonly used, expected and compromised passwords, and ASVS v5.0.0-6.2.4 and
v5.0.0-6.2.12 ask for a check against at least the 3,000 most common passwords that meet the
length rule and against a set of breached ones. Today `check_new_password` checks only the
context-specific words and the four published development passwords. A static list of common and
breached passwords, committed to the repository and read without a service call or a new
dependency, is therefore a required activation step (checklist item 5). NIST sizes the list
against the sign-in rate limit, so it need not be large.

**Enrollment: admin-issued one-time codes.** An ADMIN issues a code bound to an operator id and
role. Decision: at least 128 bits from a CSPRNG, single-use, expiring within 24 hours, and stored
only as its SHA-256 hash. [ASVS v5.0.0-6.4.1](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x15-V6-Authentication.md)
asks only that activation codes be securely random and expire after first use or a short time,
so the figures are this ADR's. A plain SHA-256 is acceptable by analogy with ASVS v5.0.0-6.5.2,
which allows a standard hash for a lookup secret of 112 bits or more. The operator redeems the
code to register a passkey and, optionally, set a fallback password; the admin never chooses or
learns that password, by analogy with ASVS v5.0.0-6.4.6, which says so of resets.

**Session lifetimes**, documented as
[ASVS v5.0.0-7.1.1](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x16-V7-Session-Management.md)
asks. Access token 15 minutes (today's `access_ttl`). Refresh token rotated on every use,
invalid after 30 minutes unused and absolutely 8 hours after sign-in. That is inside NIST's
recommended AAL2 limits (SHOULDs: an overall timeout of at most 24 hours and an inactivity
timeout of at most 1 hour, [AALs](https://pages.nist.gov/800-63-4/sp800-63b/aal/)) and at the top
of the 4–8 hour absolute range that the
[OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
(accessed 2026-10-24) gives for a full-day application. The same cheat sheet puts common idle
timeouts at 2–5 minutes for high-value applications and 15–30 for low-risk ones. This console
takes 30 because an idle session can read but cannot act: every authority action needs a fresh
passkey step-up. **Decision (renewal follows the operator):** the idle limit holds only if
renewal does. Today `useAuthRefresh.ts` renews on a timer a minute before expiry, so a refresh
token that dies after 30 minutes unused would never lapse while a tab stays open. Before
activation the console renews only after operator input since the previous renewal, and the
gateway enforces both limits itself, as OWASP asks of timeouts (checklist item 8). Step-up proof
is per action, never a reusable window. A preview grant stays 1 hour, without refresh, and dies
at activation (D4).

**Activation checklist** — every item complete before the flip:
1. Persistent RS256 keys in Secret Manager (`SYNAPSE_JWT_PRIVATE_PEM`, `_PUBLIC_PEM`, `_KID`):
   today each process mints an ephemeral key, so a restart invalidates every token.
2. WebAuthn registration, sign-in and step-up endpoints, verified against WebAuthn L3 §7, with
   any new verifier dependency checked for cost (I-1, zero cost) and for licence (CLAUDE.md's
   Dependency Rules).
3. Additive migrations. `operator_presence_attestations` is audit evidence: INSERT-only for the
   app role (I-4). `operator_credentials` and `enrollment_codes` hold state, not audit rows:
   WebAuthn §7.2 updates a credential's `signCount`, `backupState` and `uvInitialized` after an
   assertion, and a code is consumed once. Decision: the app role gets UPDATE on exactly those
   columns and a code's consumed-at column, never DELETE, and redemption is a conditional UPDATE
   (`… WHERE consumed_at IS NULL`), single-use without a race. Append-only state rows would also
   serve; the conditional UPDATE is the simpler of the two.
4. The enrollment flow, and one ADMIN enrolled out of band.
5. The static common-and-breached password list wired into `check_new_password`
   (ASVS v5.0.0-6.2.4, v5.0.0-6.2.12).
6. `SYNAPSE_OPERATORS_JSON` built with `python -m api.operator_hash`, held in Secret Manager, and
   `SYNAPSE_DEV_OPERATORS_INSECURE` proven absent from the gateway container's environment on the
   VM (ASVS v5.0.0-6.3.2).
7. Step-up wired into override, steering and HITL resolution in the gateway and the console.
8. Renewal only after operator input since the previous renewal, never on a bare timer, with the
   30-minute idle and 8-hour absolute limits enforced by the gateway.
9. Per-account sign-in rate limiting and a documented lockout policy (ASVS v5.0.0-6.1.1,
   v5.0.0-6.3.1).
10. `SYNAPSE_FIREHOSE_AUTH_REQUIRED=true` and `SYNAPSE_ALLOWED_HOSTS` set (the ADR-049 Tier-P gate).
11. One reviewed PR flips `SYNAPSE_ACCESS_MODE` to `authenticated` on the gateway **and** the
    orchestrator in `docker-compose.gcp.yml`; after deploy, `GET /api/v1/auth/mode` reads
    `authenticated`, `POST /api/v1/auth/preview` is 404, an old preview grant is 401, and
    `verify_live.py` passes.
12. CLAUDE.md, FE-INV-023 and the contract-fidelity entitlement manifest updated in the same PR.

**Before any shared host runs `open` + `act`** — a separate gate, since activation retires `act`:
1. Each action a preview grant takes is marked in the row it writes, at INSERT time: for example
   a `preview` key in `audit_escalations.human_action` and a `preview-` prefix on the stored
   token ref (see the limitation under *Consequences*). It touches the audit write paths, so it
   is its own reviewed change.

### Adjacent exposures found, not decided here

Read in the code while writing this ADR and left unfixed by it. The owner of every item is the
operator.
- **Grafana:** `/grafana/` is public on 443, and its admin password falls back to a published
  compose default, as the Postgres and Neo4j passwords do behind the firewall;
  `.env.gcp.example` publishes placeholders for all three. (read; the VM's `.env.gcp` not
  checked)
- **Prometheus:** `/prometheus/` admits `157.51.0.0/16`, which is not a private range, and
  Prometheus runs with `--web.enable-lifecycle`, so an anonymous `POST /prometheus/-/quit` from
  that range stops it. (read; the effect inferred, not probed)
- **Signing keys:** no `SYNAPSE_JWT_*` reaches the GCP gateway, so each process mints its own key
  and a restart voids every token (checklist item 1). (read)
- **Trailing-slash 307:** the console posts `/api/v1/orders` and `/api/v1/steering`, whose routes
  end in a slash, so FastAPI redirects first, probably to `http://`, which a browser on https
  blocks or follows without the bearer. (read; the scheme and the browser's behaviour inferred)
- **Steering chain:** `api/routers/steering.py` never writes `audit_steering.prev_hash` or
  `current_hash`, and no trigger does, so steering audit rows are unchained. (read)

## Consequences

- No sign-in credential is compiled into the bundle or enabled in compose: a test scans
  `frontend/src` for the development passwords and the old auto-login variables, and another
  checks that no compose file sets the insecure opt-in. Service credentials still default in
  compose (*Adjacent exposures*).
- The public console can read and cannot write. `act` exists for the local stack only, where it
  admits an anonymous decision trigger through nginx and nothing else.
- Sign-in, the operator store and the hashing CLI exist and are tested while dormant, so
  activation enables code that has run, not code that has waited.
- The orchestrator's edge guard keys on forwarding headers: it stops anything that crosses
  nginx, but not a caller that reaches the orchestrator's port directly. That port is open only to
  the IAP range by the firewall (read from terraform, not probed live). Locally, `8085:8085`
  publishes it on every host interface (read from the compose file).
- In open mode a visitor can mint any number of view grants; each is cheap and rate-limited at
  the edge, and grants nothing a visitor without one could not read through the console.
- **Limitation.** Under `open` + `act`, a preview grant's override, steering change or order is
  recorded under a `token_ref` of the same form as a signed-in operator's (for example
  `audit_escalations.operator_token_ref`), so the append-only trail cannot tell an anonymous
  visitor from an operator. No deployment writes such a row today: GCP runs `open` + `view`, and
  the local stack has no gateway. The second checklist above gates `open` + `act` on any shared
  host.

## Alternatives Rejected

- **Keep auto-login behind a build-time development flag.** A flag that ships in the bundle
  still ships the credential; a build-time switch is one mistaken build away from finding 89.
- **Rotate the credential server-side only.** The bundle would still have to carry whatever
  credential auto-login uses, and a public repository publishes it.
- **No access at all until login is finished.** Contradicts the directive: the console must open
  without login.
- **Open mode with an anonymous OPS posture in production.** Every visitor could mutate the
  audit trail; `act` is confined to the local stack.
- **JWT on the orchestrator's internal routes.** It holds none of the gateway's keys (ephemeral
  per process today); internal-only, enforced twice, closes the hole without a key-distribution
  problem.
