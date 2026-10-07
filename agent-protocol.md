# Mnemo Agent API — protocol v1

Mnemo gives an embedding vector a verifiable identity. You **embed** a vector and get back a watermarked copy with a
stable `vector_uid`; later, anyone holding a vector can **verify** whether it is one of yours, and you can read its
**lineage** (what it was derived from). Autonomous agents use Mnemo without an account and without a person: they
create a short-lived namespace, work in it, and pay per verification with USDC over [x402](https://x402.org).
Optionally, a signed-in person can later promote the namespace to a permanent account (a human-assisted handoff, §8).

- API base: `https://api.trymnemo.com`
- Machine-readable contract: [`openapi.json`](https://www.trymnemo.com/openapi.json) (OpenAPI 3.1, the six operations below)
- Orientation for agents: [`llms.txt`](https://www.trymnemo.com/llms.txt) · manifest: [`agent-manifest.json`](https://www.trymnemo.com/agent-manifest.json)
- Human sign-in (promotion, accounts, API keys): `https://www.trymnemo.com/login`

If `POST /v1/agent/namespaces` answers `404`, accountless access is not enabled on that deployment.

---

## 1. Price

**0.01 USDC per healthy verification, whether the result is positive or negative, paid via x402 on Base.**

| | |
|---|---|
| Price | 10,000 atomic USDC (6 decimals) = 0.01 USDC per verification |
| Network / asset | Base mainnet (`eip155:8453`) / USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| What is charged | one **healthy completed** `POST /v1/verify` = one verification, `verified: true` **or** `verified: false` |
| Free | creating and reading a namespace, embedding, lineage reads, promotion, refused or malformed requests, rate-limited requests, and any verification Mnemo fails to complete (`503`) |
| Included free verifications | none for an accountless namespace. A promoted namespace becomes an ordinary account on the free plan, with that plan's monthly verification allowance |

Each payment buys exactly one verification. A verification Mnemo fails to complete costs nothing, and the payment stays
usable for the retry (§6). A replay of a request you already paid for creates no second payment, credit or charge.

**The authentication mode picks the commercial path.** This price and x402 apply only to calls authenticated with a
namespace capability (accountless). A call with an account API key — including a promoted namespace's — uses that
account's subscription plan instead: included monthly verifications, no automatic overage and no top-ups. When the
plan's verifications are used up, verify answers `402 {"code": "insufficient_credits"}` **without** `PAYMENT-REQUIRED`;
x402 is never offered to an API key, and a `PAYMENT-SIGNATURE` sent with one is ignored.

## 2. Authentication

| Credential | Header | Who has it | Used for |
|---|---|---|---|
| **Capability** | `X-Mnemo-Capability: mnemo_eph_…` | the agent; returned **once** when the namespace is created | every call on that namespace until it expires or is promoted |
| **API key** | `X-API-Key: …` | an account (a promoted namespace receives one; developers create them in the dashboard) | `POST /v1/embed`, `POST /v1/verify`, `GET /v1/lineage/{vector_uid}` on a permanent account, under that account's subscription plan ([pricing](https://www.trymnemo.com/pricing)); never x402 |
| **Human session** | `Authorization: Bearer …` | a person signed in at `https://www.trymnemo.com/login` | only promotion, together with the capability |

The capability is a secret: Mnemo stores only a digest of it and cannot show it again. It stops authenticating at the
namespace's `expires_at`. A capability can call only the six operations below; anything else answers `403`.

A request with **no credential** answers `403` (`Authentication required`). A capability that is **invalid or
expired** (unknown, revoked by a completed promotion, or past `expires_at`) answers `401`. Promotion is the exception:
a missing capability or a missing human session there answers `401` (§8).

## 3. Operations

All bodies are JSON. Vectors are arrays of 512–4096 finite numbers.

| # | Method | Path | Auth | Cost | Purpose |
|---|---|---|---|---|---|
| 1 | POST | `/v1/agent/namespaces` | none | free | create an ephemeral namespace; returns the capability once |
| 2 | GET | `/v1/agent/namespace` | capability | free | namespace state, expiry, usage and limits |
| 3 | POST | `/v1/embed` | capability or API key | free | watermark a vector and register it; optional verified `parent` |
| 4 | GET | `/v1/lineage/{vector_uid}` | capability or API key | free | the verified derivation chain of an object |
| 5 | POST | `/v1/verify` | capability (paid) or API key | with a capability: 0.01 USDC per healthy verification (x402); with an API key: the account's plan, never x402 | is this vector one of this namespace's objects? |
| 6 | POST | `/v1/agent/namespace/promote` | capability **and** human session | free | optional, human-assisted: turn the namespace into a permanent account; identities and lineage preserved |

### 3.1 Create a namespace — `POST /v1/agent/namespaces`

Send a JSON body; every field in it is optional, so `{}` is enough: `{"ttl_seconds": 86400, "agent_id": "my-agent"}`. `ttl_seconds` defaults to 86,400 (24 h); it must be
60–259,200 (72 h) — anything outside is refused with `400 EPHEMERAL_LIFETIME_UNSUPPORTED`, never shortened. `agent_id`
(≤ 128 characters) is a label only; it grants nothing.

`201`:

```json
{
  "tenant_id": "machine_ephem:EXAMPLE_TENANT_ID",
  "capability": "mnemo_eph_EXAMPLE_CAPABILITY_DO_NOT_USE",
  "storage_class": "ephemeral",
  "durable": false,
  "state": "ACTIVE",
  "expires_at": "2026-10-07T12:00:00Z",
  "ttl_seconds": 86400,
  "object_limit": 10000,
  "byte_limit": 26214400,
  "objects_used": 0,
  "bytes_used": 0,
  "upgrade_available": true
}
```

Store the `capability` now; it is never shown again.

### 3.2 Namespace status — `GET /v1/agent/namespace`

Returns `tenant_id`, `storage_class`, `durable`, `state`, `expires_at`, `seconds_remaining`, `objects_used`,
`objects_limit`, `bytes_used`, `bytes_limit`, `upgrade_available`, and — once — `warning` (§4).

### 3.3 Embed — `POST /v1/embed`

```json
{"vector": [0.0123, -0.0456, "…512 to 4096 numbers…"], "model_id": "text-embedding-3-small", "model_version": "1.0",
 "request_id": "0b6f8f3e-3c55-4f0e-9c1a-7d2b6a4e9f10"}
```

`200`: `vector_uid`, `watermarked_vector` (store **this** vector, not your original — it carries the identity),
`created_at`, `dimensions`, and on a namespace also `namespace_expires_at` and `namespace_state`. Optional fields:
`parent` (§7) → response `lineage {parent_uid, relation, depth}`; `subject` (a `{subject_uri, subject_type}` description
of what the vector represents) → response `subject_proof`, which you pass back unchanged as `subject_proof` on verify.

### 3.4 Lineage — `GET /v1/lineage/{vector_uid}`

`200` with the complete verified chain, or `409` when the chain is broken (§7).

### 3.5 Verify — `POST /v1/verify`

```json
{"vector": [0.0123, -0.0456, "…"]}
```

On a namespace with no paid credit this answers `402` with x402 payment requirements; pay and send it again (§5).
Leave `request_id` out of a paid verify: the payment identifies the operation, so every retry can resend the identical
body (§6).
`200`:

```json
{"verified": true, "confidence": 0.97, "vector_uid": "EXAMPLE-VECTOR-UID", "policy_ok": true,
 "signals": {"mode": "STRICT"}, "lineage": {"has_parent": false, "parent_uid": null, "depth": 0}}
```

A `200` with `verified: false`, `vector_uid: null`, `policy_ok: false` and `lineage: null` is a **healthy negative
result**: the verification ran and the vector is not one of this namespace's objects. It is charged like a positive
one; do not pay again for the same vector. Decide on `verified`: `policy_ok` is a separate policy signal, always
`false` on a negative and not a verdict on its own. `lineage`
is present only for a verified object (`null` means unknown, not "root"). `signals` is diagnostic metadata about how
the result was reached; it is informational and its fields may change. A verification Mnemo could not complete is never
a `200`: it is `503 {"code": "verification_unavailable"}`, carries no result, costs nothing, and is retried (§6).

### 3.6 Promote — `POST /v1/agent/namespace/promote`

Optional and human-assisted; an autonomous agent never needs it. See §8.

## 4. Namespace lifecycle

- **Lifetime** is fixed at creation: default 24 h, 60 s to 72 h. Activity does **not** extend it, and there is no
  renewal.
- `expires_at` is returned at creation, on every embed (`namespace_expires_at`), and by the status call.
- **One warning**: the first status or embed response after 75% of the lifetime has passed carries, once,
  `"warning": {"code": "EPHEMERAL_STORAGE_EXPIRING", "expires_at": "…", "seconds_remaining": …,
  "action_required": "upgrade_to_persistent", "data_after_expiry": "purged"}`. Mnemo never contacts the agent.
  `action_required` is advisory: nothing is required unless you want to keep the data, which needs a person to
  promote the namespace (§8).
- **At `expires_at`** the capability stops authenticating (`401`), embeds are refused (`410
  EPHEMERAL_NAMESPACE_EXPIRED`), and the namespace's data is purged. Nothing is kept for a namespace that was not
  promoted.
- A paid verification needs at least **120 s** of lifetime left; closer to expiry it is refused (`402
  insufficient_credits`, no payment requested). Promotion needs at least **5 minutes** left.
- **Per namespace**: at most 10,000 objects and 26,214,400 accounted bytes (25 MiB). One object accounts for
  `4 × dimensions + 512` bytes, plus the size of its `subject`.

## 5. Paying with x402

Mnemo implements x402 V2 (`exact` scheme, EVM, EIP-3009 `transferWithAuthorization`, settlement **before** the
verification). Any standard x402 V2 client can pay.

1. `POST /v1/verify` with the capability and your body. With no paid credit the answer is
   `402 {"code": "insufficient_credits"}` and a **`PAYMENT-REQUIRED`** header: base64-encoded JSON.
2. Decode it. It contains `x402Version: 2`, `resource {url: "/v1/verify"}` and one entry in `accepts`:

   ```json
   {"scheme": "exact", "network": "eip155:8453",
    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "amount": "10000",
    "payTo": "0xPAY_TO_FROM_THE_402", "maxTimeoutSeconds": 120,
    "extra": {"paymentFlow": "upfront", "assetTransferMethod": "eip3009", "decimals": 6,
              "name": "USD Coin", "version": "2"}}
   ```

   Take every value — especially `payTo` and `amount` — from the 402 you received; do not hard-code them. `name` and
   `version` are the USDC EIP-712 signing domain (with chain id 8453 and the asset as the verifying contract).
3. Sign an EIP-3009 `TransferWithAuthorization` for exactly that amount to exactly that `payTo`, with your wallet:
   EIP-712 domain `{name, version}` from `extra`, `chainId` 8453, `verifyingContract` = `asset`; message
   `{from, to, value, validAfter, validBefore, nonce}` with `to` = `payTo`, `value` = `amount`, a fresh random 32-byte
   `nonce`, `validAfter` already passed (standard clients send `0`) and `validBefore` shortly in the future (standard
   clients use now + `maxTimeoutSeconds`). An expired or not-yet-valid authorization is refused.
4. Send the **same request again** — the identical body — with the signed payment in
   **`PAYMENT-SIGNATURE`**: base64 of this JSON (any standard x402 V2 client builds it for you):

   ```json
   {"x402Version": 2,
    "payload": {"authorization": {"from": "0xYOUR_WALLET", "to": "0xPAY_TO_FROM_THE_402", "value": "10000",
                                  "validAfter": "0", "validBefore": "1791000120", "nonce": "0xRANDOM_32_BYTE_NONCE"},
                "signature": "0xYOUR_EIP712_SIGNATURE"},
    "accepted": {"…": "the accepts entry from the 402, unchanged"},
    "resource": {"url": "/v1/verify", "…": "the resource from the 402, unchanged"}}
   ```

5. Mnemo checks the payment against its own configuration, settles it, and runs the verification. Only the `200` of a
   verification paid on that request carries **`PAYMENT-RESPONSE`** (base64 JSON: `success`, `transaction`, `network`,
   `payer`); a `200` paid from a credit you already hold, or a replayed result, does not.

A `402 {"code": "insufficient_credits"}` **without** `PAYMENT-REQUIRED`, after you sent a payment, means this request
was not funded and no verification ran. It does not say whether money moved: the payment may have been refused (wrong
amount, recipient, asset or network, a bad signature, too little balance), or its settlement may not be final yet.
Resend the identical body with the same `PAYMENT-SIGNATURE`: one authorization is only ever one payment, and a payment
that did settle is used without paying again. A settlement that was not final is confirmed only once Base finalizes
it, which can take far longer than the authorization's `validBefore`; until then the same signature keeps getting this
`402`.

**Stopping rule.** Resend with backoff (for example after 30 s, then every 5 minutes). Stop when you get a `200`, or
when the same signature still gets this `402` **90 minutes after its `validBefore`**: that authorization has not funded
this request. **Do not create a second authorization automatically.** A new authorization is a second, independent
payment, so sign one only as a deliberate decision to pay again. To get the requirements for it, send the request
without `PAYMENT-SIGNATURE`.

**Late settlement.** If the first payment settles after all (after you stopped, or after you paid again), Mnemo
credits it to this namespace. The next verify in this namespace, sent without `PAYMENT-SIGNATURE`, uses that credit
and answers `200` without asking for payment. A credit can be spent only by a verify in this namespace before its
`expires_at` (§4); it does not move to another namespace.

Mnemo never asks a namespace that already has a paid credit to pay again, and a payment is never accepted for a
different amount, asset, network or recipient.

## 6. Retries and idempotency

For a paid verify the payment identifies the operation. The simplest correct client builds **one body per
verification, without `request_id`**, and resends that identical body with the same `PAYMENT-SIGNATURE` in every case
below.

| Situation | What to do | Charged |
|---|---|---|
| `402` with `PAYMENT-REQUIRED` | pay and resend the identical body with `PAYMENT-SIGNATURE` (a `402` does not use up a `request_id`) | once, on the `200` |
| `503 verification_unavailable` after you paid | resend the identical body with the **same `PAYMENT-SIGNATURE`**. Your settled payment is used; you do not pay again | once, on the healthy `200` |
| No response (timeout, dropped connection) after a paid request | resend the identical body with the same `PAYMENT-SIGNATURE`. If the first one finished you get its stored result; otherwise it runs now | once |
| `409 request_in_progress` | an earlier attempt with this payment is still running. Wait a moment, then resend the identical body with the same `PAYMENT-SIGNATURE`: you get that attempt's result, or it runs now if that attempt failed | once |
| `402` without `PAYMENT-REQUIRED` after you paid | this request was not funded (§5). Resend the identical body with the same `PAYMENT-SIGNATURE`, with backoff; stop 90 minutes after its `validBefore`. Never create a second authorization automatically | once per payment that settles; one confirmed late becomes a credit for a later verify in this namespace |
| Namespace expired after your payment was accepted, before you got the result | within one hour of the payment, resend with the same capability and `PAYMENT-SIGNATURE` the body **exactly as first sent with that payment**; Mnemo refuses any other body (`401`). You get the result you paid for. This works only for a paid verify sent without your own `Idempotency-Key`, and only while the namespace's data is still held (otherwise `409 PAYMENT_UNRECOVERABLE_PAYLOAD_PURGED`) | once |
| `409 Duplicate request_id` | that `request_id` was already used by a request that ran (or is running); use a new one, or leave it out | — |
| `409 idempotency_key_reused` | that payment (or `Idempotency-Key`) already bought a verification of a **different** vector; request again without payment: it uses any credit you still hold, otherwise you get a new `402` and pay again | — |

- `request_id` (optional, in the body) protects against double submission: a request that ran keeps it for 24 hours.
  Only a request that ended in `402` releases it. It is **not** scoped to your namespace. If you send one, use a fresh
  random UUID, never a fixed or sequential value. On a paid verify that is why leaving it out is simpler: with one,
  every retry after the request has run (`503`, a timeout, `409 request_in_progress`) needs a new `request_id`, while
  the post-expiry recovery above accepts only the original body.
- `Idempotency-Key` (optional header) makes a verify replayable: the same key with the same body returns the stored
  result without running again or charging again. For a paid accountless verify, the payment itself plays this role
  unless you send your own key.
- A replay never creates a second settlement, credit or charge.
- Leave margin before `expires_at`: a paid verification, including a retry of a payment you already made, is refused
  when fewer than 120 s of lifetime remain (§4). A credit does not move to another namespace: if you already paid in
  that window, do not pay again in a new namespace; after `expires_at` the recovery row above applies to that payment.

## 7. Lineage

To record that an object was derived from another, embed it with a `parent`:

```json
{"vector": ["…the derived vector…"], "model_id": "m",
 "parent": {"vector_uid": "PARENT-VECTOR-UID", "relation": "summary", "vector": ["…the parent's watermarked vector as you hold it…"]}}
```

`relation` is one of `re_embed`, `summary`, `chunk`, `translation`, `transform`. Mnemo verifies the parent (it must be an
object of the same namespace or account, and the vector you send must verify as exactly that object) before it creates
the child; otherwise `403 LINEAGE_PARENT_NOT_VERIFIED`. Chains are at most 64 deep (`409 LINEAGE_DEPTH_EXCEEDED`).

`GET /v1/lineage/{vector_uid}` re-verifies the chain on every read and returns `{vector_uid, chain_ok: true, complete,
depth, ancestors: [{vector_uid, relation}, …]}` (parent first), or `409` with `chain_ok: false` and an `error` when a link
does not verify. An object that does not exist or is not yours is `404 LINEAGE_NOT_FOUND`. Lineage reads are free.

## 8. Promotion (optional, human-assisted)

Promotion is optional. Everything in §§3–7 works without it and without a person; an agent that only needs Mnemo for
the life of its namespace never promotes. Promotion turns the namespace into a permanent account without re-embedding
anything: the same `tenant_id`, the same `vector_uid`s, the same watermarked vectors and the same lineage.

It is a **human-assisted handoff**: an agent cannot promote on its own. The call needs the namespace capability **and**
the session of a person signed in to Mnemo, so the agent and that person must bring the two together. In v1 the call is
made directly against the API; the website has no promotion page.

1. A person signs in at `https://www.trymnemo.com/login`. Promotion needs that person's session token: it binds the
   new account to them.
2. `POST /v1/agent/namespace/promote` with **both** headers: `X-Mnemo-Capability: <the namespace capability>` and
   `Authorization: Bearer <the person's session token>`. No body.
3. The namespace must be `ACTIVE` with at least 5 minutes left (`409 TOO_LATE_TO_PROMOTE` otherwise). After
   `expires_at` the capability no longer authenticates (`401`) and the namespace cannot be promoted.

`200`:

```json
{"tenant_id": "machine_ephem:EXAMPLE_TENANT_ID", "lifecycle_state": "PERSISTENT", "durable": true,
 "storage_class": "persistent", "object_count": 3, "tier": "free", "retention_seconds": 2592000,
 "already_persistent": false, "credential_id": "EXAMPLE-CREDENTIAL-ID", "credential": "EXAMPLE_ONE_TIME_API_KEY"}
```

`credential` appears **once**: it is the account's API key (`X-API-Key`); store it immediately. After a `200` the
capability is revoked, so a repeated call answers `401` and issues nothing. If a promotion call fails (`5xx`, for
example `503 PROMOTION_FAILED`), check `GET /v1/agent/namespace`:

- `state` `ACTIVE`: nothing was started. The same person repeats the call while at least 5 minutes remain; otherwise
  the data is purged at `expires_at` like any namespace.
- `state` `PROMOTING`: the promotion had started, and Mnemo completes it — through a prompt repeat by the same person,
  or in the background. A repeat that completes issues a fresh credential and revokes any earlier one. A background
  completion issues no credential through this API; afterwards the capability answers `401` and the data is kept.
- `state` `PERSISTENT`: the promotion completed but its response was lost. The same person repeats the call promptly
  to receive a fresh credential (any earlier one is revoked).
- `401`: the capability no longer authenticates. Either the promotion was completed (data kept) or the namespace
  expired before promotion began (data purged); this API does not tell the two apart.

Promotion is free.

Promotion is not "kept forever": the account's objects follow the retention of its plan (§9).

## 9. Retention

An object stays verifiable for its plan's retention, counted from when it was stored — for a promoted namespace, from
promotion:

| Plan | Retention |
|---|---|
| Free | 30 days |
| Starter | 90 days |
| Growth | 365 days |
| Scale | 1,095 days |
| Pro (legacy) | 365 days |
| Enterprise | indefinite |

Upgrading later does not extend the retention of objects already stored. After an object's retention ends, verifying it
returns `verified: false` (a healthy negative result). Its lineage records may remain readable, but that is not
guaranteed. An ephemeral namespace that is not promoted keeps nothing after `expires_at` (§4).

## 10. Limits

| Limit | Value | When exceeded |
|---|---|---|
| Requests per namespace (all capability calls together) | 120 per minute | `429`, `Retry-After: 60` |
| Namespace creation requests per source address | 5 per clock hour; every well-formed request that reaches the limit counts, including ones then refused with `429` or `503` | `429`, `Retry-After: 3600` |
| Objects per namespace | 10,000 | `413 NAMESPACE_OBJECT_LIMIT` |
| Accounted bytes per namespace | 25 MiB (26,214,400) | `413 NAMESPACE_BYTE_LIMIT` |
| Namespace lifetime | 60 s – 72 h, default 24 h | `400 EPHEMERAL_LIFETIME_UNSUPPORTED` |
| Vector dimensions | 512 – 4096 | `400 vector_dimension_unsupported` |
| Request body | 256 KiB (embed with a capability); 4 KiB (namespace creation) | `413 REQUEST_BODY_TOO_LARGE` |
| Lineage depth | 64 | `409 LINEAGE_DEPTH_EXCEEDED` |

Mnemo also protects shared capacity: when it is temporarily full, creation answers `503 EPHEMERAL_CAPACITY_EXHAUSTED`
and an embed can answer `413 GLOBAL_BYTE_LIMIT`. Retry later, backing off for minutes rather than seconds: each
creation retry may use one of the 5 hourly creation requests.

## 11. Errors

Most errors are `{"detail": …}` (a string, or an object with a `code`). Billing refusals on verify are a bare
`{"code": …}`.

| Status | Meaning | What to do |
|---|---|---|
| `400` | malformed input: `vector_dimension_unsupported`, `vector_nonfinite`, `vector_magnitude_extreme`, `vector_zero_norm`, `vector_near_constant`, `idempotency_key_invalid`, `EPHEMERAL_LIFETIME_UNSUPPORTED` | fix the request |
| `401` | invalid or expired capability (unknown, revoked by a completed promotion, or past `expires_at`); invalid API key; on promotion, also a missing capability (`CAPABILITY_REQUIRED`) or a missing human session | a namespace past `expires_at` cannot be used; create a new one. After a promotion attempt, see §8 |
| `402` | `insufficient_credits` with `PAYMENT-REQUIRED`: pay (§5). Bare `{"code": "insufficient_credits"}` without the header after you sent a payment: this request was not funded (§5, §6). `{"detail": {"code": "insufficient_credits", …}}`: too close to expiry to pay. `ACCOUNTLESS_VERIFY_NOT_ENABLED`: paid verification is not enabled | pay, resend with the same payment, or create a new namespace |
| `403` | no credential at all (`Authentication required`); the capability may not call this path; `LINEAGE_PARENT_NOT_VERIFIED`; promotion by someone other than the person who started it | send the capability in `X-Mnemo-Capability` |
| `404` | accountless access not enabled; `LINEAGE_NOT_FOUND` | — |
| `409` | `Duplicate request_id`, `idempotency_key_reused`, `request_in_progress`, `PAYMENT_UNRECOVERABLE_PAYLOAD_PURGED`, a broken lineage chain, `TOO_LATE_TO_PROMOTE`, `PROMOTION_IN_PROGRESS`, `EPHEMERAL_NAMESPACE_PROMOTING` | see §6–§8 |
| `410` | `EPHEMERAL_NAMESPACE_EXPIRED`; `SOURCE_EXPIRED` / `SOURCE_GONE` (a promotion call that raced the namespace's expiry) | create a new namespace |
| `413` | a namespace limit or the body size limit | — |
| `422` | the body has unknown or mistyped fields | fix the request |
| `429` | rate limit | wait `Retry-After` seconds |
| `503` | `verification_unavailable` (not charged — retry, §6), `billing_unavailable`, `EPHEMERAL_CAPACITY_EXHAUSTED`, `EPHEMERAL_INFRASTRUCTURE_UNAVAILABLE`, `LINEAGE_UNAVAILABLE` | retry with backoff |

## 12. Walkthrough

Complete, runnable versions: [`examples/agent-quickstart.sh`](examples/agent-quickstart.sh) (curl) and
[`examples/agent_quickstart.py`](examples/agent_quickstart.py) (Python). In short:

```bash
API=https://api.trymnemo.com

# 1. create a namespace (store the capability)
curl -s -X POST $API/v1/agent/namespaces -H 'Content-Type: application/json' -d '{"ttl_seconds": 86400}'
CAP=mnemo_eph_EXAMPLE_CAPABILITY_DO_NOT_USE

# 2. embed (store watermarked_vector and vector_uid)
curl -s -X POST $API/v1/embed -H "X-Mnemo-Capability: $CAP" -H 'Content-Type: application/json' \
  -d '{"vector": [ …768 numbers… ], "model_id": "my-model", "request_id": "'"$(uuidgen)"'"}'

# 3. status
curl -s $API/v1/agent/namespace -H "X-Mnemo-Capability: $CAP"

# 4. lineage
curl -s $API/v1/lineage/EXAMPLE-VECTOR-UID -H "X-Mnemo-Capability: $CAP"

# 5. verify → 402 with PAYMENT-REQUIRED (no request_id on a paid verify: retries resend the identical body)
curl -s -i -X POST $API/v1/verify -H "X-Mnemo-Capability: $CAP" -H 'Content-Type: application/json' \
  -d '{"vector": [ …the watermarked vector… ]}'

# 6. pay with an x402 client, then send the SAME request again with PAYMENT-SIGNATURE → 200 + PAYMENT-RESPONSE
curl -s -i -X POST $API/v1/verify -H "X-Mnemo-Capability: $CAP" -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE" \
  -H 'Content-Type: application/json' -d '{"vector": [ …the same watermarked vector… ]}'
```

## 13. Not in v1

- **MCP**: MCP support is planned; there is no public MCP server today. Use the HTTP API.
- Renewing or extending an ephemeral namespace (to keep its data, a signed-in person can promote it, §8).
- Notifications, webhooks or callbacks — Mnemo never contacts an agent.
- Payment assets other than USDC, networks other than Base, and payment schemes other than x402 `exact` with EIP-3009.
