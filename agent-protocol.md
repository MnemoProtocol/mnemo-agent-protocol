# Mnemo Agent API — protocol v1

Mnemo gives an embedding vector a verifiable identity. You **embed** a vector and get back a watermarked copy with a
stable `vector_uid`. Later, you — with the same namespace capability or account API key — can **verify** a vector you
hold: Mnemo Verify checks whether a submitted vector resolves to an object registered to the caller's Mnemo account or
namespace. You can also read an object's **lineage** (what it was derived from). Results are scoped to your own account
or namespace: verify cannot tell you whether a vector belongs to someone else, and Mnemo does not establish the truth,
authorship or ownership of the content a vector represents. Autonomous agents use Mnemo without an account and without
a person: they create a short-lived namespace, work in it, and pay for verification with USDC over
[x402](https://x402.org) on Base, with USDC.e over [MPP](https://mpp.dev) on Tempo, or — for the 500-verification burst
only — with a card through MPP and a Stripe Shared Payment Token. No rail is required; use the one your wallet supports.
Optionally, a signed-in person can later promote the namespace to a permanent account (a human-assisted handoff, §8).

- API base: `https://api.trymnemo.com`
- Machine-readable contract: [`openapi.json`](https://www.trymnemo.com/openapi.json) (OpenAPI 3.1, the seven operations below)
- Orientation for agents: [`llms.txt`](https://www.trymnemo.com/llms.txt) · manifest: [`agent-manifest.json`](https://www.trymnemo.com/agent-manifest.json)
- Human sign-in (promotion, accounts, API keys): `https://www.trymnemo.com/login`
- Python SDK for the account API-key path (no x402, no lineage): `pip install mnemo-protocol`, imported as
  `from mnemo_sdk import MnemoClient` ([PyPI](https://pypi.org/project/mnemo-protocol/),
  [source](https://github.com/MnemoProtocol/mnemo-sdk))

If `POST /v1/agent/namespaces` answers `404`, accountless access is not enabled on that deployment.

**When not to use Mnemo.** It is not for vectors that were not embedded through Mnemo in your own namespace or account;
not for checking whether a vector belongs to another party; not an embedding model, a vector database or similarity
search; not for judging the truth, authorship, ownership or source model of content, or the authenticity of files,
images, code or text. Accountless access (on any payment rail) must not be used for personal data subject to EEA, UK or
Swiss data protection law.

---

## 1. Price

**0.01 USDC per healthy verification, whether the result is positive or negative, paid via x402 on Base** — or the
same 0.01 USD in USDC.e over MPP on Tempo. A namespace can instead buy **500 verifications for 5.00 USD** at once.

| Offer | Price | You get | Bought at | Rails |
|---|---|---|---|---|
| `single_verify` | 0.01 USD | one healthy verification | the `402` of `POST /v1/verify` (§3.5) | x402 (USDC, Base); MPP Tempo (USDC.e) |
| `burst_500` | 5.00 USD | 500 verifications for this namespace, usable for 14 days, and a 100,000,000-byte storage allowance (§4.1) | `POST /v1/agent/namespace/fund` (§3.7) | x402 (USDC, Base); MPP Tempo (USDC.e); MPP card (Stripe Shared Payment Token) |

The rail is only how you pay: for a given offer every rail buys exactly the same thing. A card is accepted for
`burst_500` only — Stripe's minimum card charge (0.50 USD) rules out a one-cent card payment. Which offers and rails this
namespace can buy right now is listed by `GET /v1/agent/namespace` in `payment_menu` (§3.2); each `402` challenge is
authoritative for the exact amount, asset, network and recipient.

| | |
|---|---|
| `single_verify` amount | 10,000 atomic units (6 decimals) = 0.01 USD |
| `burst_500` amount | 5,000,000 atomic units (6 decimals) on x402 and Tempo; 500 (US cents) on a card |
| x402 network / asset | Base mainnet (`eip155:8453`) / USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| MPP Tempo network / asset | Tempo mainnet (chain `4217`, `eip155:4217`) / USDC.e `0x20c000000000000000000000b9537d11c60e8b50` |
| MPP card | Stripe Shared Payment Token, USD; `burst_500` only |
| What is charged | one **healthy completed** `POST /v1/verify` = one verification, `verified: true` **or** `verified: false` |
| Free | creating and reading a namespace, embedding, lineage reads, promotion, refused or malformed requests, rate-limited requests, and any verification Mnemo fails to complete (`503`) |
| Included free verifications | none for an accountless namespace, and none after promotion: promoting a namespace does not start the free trial. The promoted account's API key uses the account's subscription plan; until the account has one, its calls can be refused with `402 {"code": "insufficient_credits"}` (no x402 fallback, §8) |

A `single_verify` payment buys exactly one verification; a `burst_500` payment buys 500. A verification Mnemo fails to
complete costs nothing, and the payment (or credit) stays usable for the retry (§6). A replay of a request you already
paid for creates no second payment, credit or charge.

**The authentication mode picks the commercial path.** These offers and every payment rail apply only to calls
authenticated with a namespace capability (accountless). A call with an account API key — including a promoted
namespace's — uses that account's subscription plan instead: included monthly verifications, no automatic overage and
no top-ups. When the plan's verifications are used up, verify answers `402 {"code": "insufficient_credits"}` **without**
`PAYMENT-REQUIRED`; x402 is never offered to an API key, and neither is any other rail: a `PAYMENT-SIGNATURE` sent with
one is ignored.

## 2. Authentication

| Credential | Header | Who has it | Used for |
|---|---|---|---|
| **Capability** | `X-Mnemo-Capability: mnemo_eph_…` | the agent; returned **once** when the namespace is created | every call on that namespace until it expires or is promoted |
| **API key** | `X-API-Key: …` | an account (a promoted namespace receives one; developers create them in the dashboard) | `POST /v1/embed`, `POST /v1/verify`, `GET /v1/lineage/{vector_uid}` on a permanent account, under that account's subscription plan ([pricing](https://www.trymnemo.com/pricing)); never x402 |
| **Human session** | `Authorization: Bearer …` | a person signed in at `https://www.trymnemo.com/login` | only promotion, together with the capability |

The capability is a secret: Mnemo stores only a digest of it and cannot show it again. It stops authenticating at the
namespace's `expires_at` — or, for a funded namespace (§4.1), at `retained_until`. A capability can call only the seven operations below; anything else answers `403`.

A request with **no credential** answers `403` (`Authentication required`). A capability that is **invalid or
expired** (unknown, revoked by a completed promotion, or past `expires_at` — for a funded namespace, past `retained_until`) answers `401`. Promotion is the exception:
a missing capability or a missing human session there answers `401` (§8).

## 3. Operations

All bodies are JSON. Vectors are arrays of 512–4096 finite numbers.

**Vector contract.** You supply the vector; Mnemo does not compute embeddings, and `model_id` is a label you declare,
not something Mnemo runs or attests.

- **Input**: the FP32 embedding your model produced, 512–4096 finite numbers. Unit-norm (L2-normalized) input is the
  expected form; Mnemo L2-normalizes whatever it receives before watermarking.
- **Output**: `watermarked_vector` is a unit-length watermarked copy of your input with the same number of dimensions.
  It is **measurably perturbed** from your input — not your original vector. Store and use this copy in place of the
  original: it is the vector to keep and verify. Similarity scores computed with it differ from scores computed with the
  original, so re-check any thresholds you tuned on the originals.
- **Verify** the copy you stored. A vector changed too much after embedding can come back as a healthy negative (§3.5).

| # | Method | Path | Auth | Cost | Purpose |
|---|---|---|---|---|---|
| 1 | POST | `/v1/agent/namespaces` | none | free | create an ephemeral namespace; returns the capability once |
| 2 | GET | `/v1/agent/namespace` | capability | free | namespace state, expiry, usage and limits |
| 3 | POST | `/v1/embed` | capability or API key | free | watermark a vector and register it; optional verified `parent` |
| 4 | GET | `/v1/lineage/{vector_uid}` | capability or API key | free | the verified derivation chain of an object |
| 5 | POST | `/v1/verify` | capability (paid) or API key | with a capability: 0.01 USD per healthy verification (x402 or MPP Tempo), or one credit of a `burst_500`; with an API key: the account's plan, never x402 | does this vector resolve to an object registered to this namespace or account? |
| 6 | POST | `/v1/agent/namespace/promote` | capability **and** human session | free | optional, human-assisted: turn the namespace into a permanent account; identities and lineage preserved |
| 7 | POST | `/v1/agent/namespace/fund` | capability (paid) | 5.00 USD (x402, MPP Tempo or MPP card) | buy `burst_500` for this namespace: 500 verifications, a 14-day funded window, 100,000,000 bytes (§3.7, §4.1) |

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

Store the `capability` now; it is never shown again. The `201` also carries the Terms of Service `Link` header (§5).

### 3.2 Namespace status — `GET /v1/agent/namespace`

Returns `tenant_id`, `storage_class`, `durable`, `state`, `expires_at`, `seconds_remaining`, `objects_used`,
`objects_limit`, `bytes_used`, `bytes_limit`, `upgrade_available`, and — once — `warning` (§4). A funded namespace
(§4.1) also returns `funded_until`, `retained_until` and `retained_seconds_remaining`.

**`payment_menu`** — the authoritative list of what this namespace can buy **right now**, and over which rails. It is
computed from the payment rails that are accepting payments at that moment, so a rail is listed only while it takes
payments, and an offer that is not listed cannot be bought now. The namespace's own limits apply: nothing is listed too
close to expiry, and a funded namespace is offered refills only, never `single_verify`. A listed `burst_500` can still be answered `503
funded_capacity_unavailable` (no capacity for a new burst: no challenge, nothing charged) or `503 payment_processing` (a
burst payment of this namespace is already being confirmed: resend it, do not pay again). Each entry:

```json
{"payment_menu": [
  {"id": "single_verify", "price_usd": "0.01", "credits": 1, "route": "POST /v1/verify",
   "rails": [{"id": "x402", "protocol": "x402", "scheme": "exact", "header": "PAYMENT-SIGNATURE", "network": "eip155:8453"},
             {"id": "mpp_tempo", "protocol": "mpp", "method": "tempo", "intent": "charge", "header": "Authorization: Payment", "network": "eip155:4217"}]},
  {"id": "burst_500", "price_usd": "5.00", "credits": 500, "funded_window_days": 14, "grace_hours": 24,
   "storage_allowance_bytes": 100000000, "route": "POST /v1/agent/namespace/fund",
   "rails": [{"id": "x402", "…": "…"}, {"id": "mpp_tempo", "…": "…"},
             {"id": "stripe_spt", "protocol": "mpp", "method": "stripe", "intent": "charge", "header": "Authorization: Payment"}]}]}
```

The menu says what to buy and where; the route's `402` says exactly how to pay (amount, asset, recipient).

### 3.3 Embed — `POST /v1/embed`

```json
{"vector": [0.0123, -0.0456, "…512 to 4096 numbers…"], "model_id": "text-embedding-3-small", "model_version": "1.0",
 "request_id": "0b6f8f3e-3c55-4f0e-9c1a-7d2b6a4e9f10"}
```

`200`: `vector_uid`, `watermarked_vector` (a measurably perturbed, unit-length watermarked copy of your input: store and
use **this** vector, not your original — it carries the identity; see the vector contract above),
`created_at`, `dimensions`, and on a namespace also `namespace_expires_at` and `namespace_state`. Optional fields:
`parent` (§7) → response `lineage {parent_uid, relation, depth}`; `subject` (a `{subject_uri, subject_type}` description
of what the vector represents) → response `subject_proof`, which you pass back unchanged as `subject_proof` on verify.

### 3.4 Lineage — `GET /v1/lineage/{vector_uid}`

`200` with the complete verified chain, or `409` when the chain is broken (§7).

### 3.5 Verify — `POST /v1/verify`

```json
{"vector": [0.0123, -0.0456, "…"]}
```

On a namespace with no paid credit this answers `402` with the challenge of each rail accepting payment —
`PAYMENT-REQUIRED` (x402) and/or one `WWW-Authenticate: Payment` per MPP method; pay with one of them and send it again
(§5).
Leave `request_id` out of a paid verify: the payment identifies the operation, so every retry can resend the identical
body (§6). A funded namespace (§4.1) verifies on its burst credits and is never offered a single verification.
`200`:

```json
{"verified": true, "confidence": 0.97, "vector_uid": "EXAMPLE-VECTOR-UID", "policy_ok": true,
 "signals": {"mode": "STRICT"}, "lineage": {"has_parent": false, "parent_uid": null, "depth": 0}}
```

`verified: true` means the vector resolved to an object registered to this namespace or account; `vector_uid` is that
object's id. It says nothing about the content the vector represents: not its truth, authorship or ownership.

A `200` with `verified: false`, `vector_uid: null`, `policy_ok: false` and `lineage: null` is a **healthy negative
result**: the verification ran, and attribution to one of this namespace's or account's registered objects could not be
shown — for example the vector was never embedded here, it was changed too much after embedding, or its object's
retention has ended (§9). It is a safe outcome, not an error, and not proof that the vector belongs to someone else. It
is charged like a positive one; do not pay again for the same vector. Decide on `verified`: `policy_ok` is a separate
policy signal, always `false` on a negative and not a verdict on its own. `confidence` is a diagnostic score that
accompanies the verdict; it is not a probability and not a threshold to apply yourself. `lineage`
is present only for a verified object (`null` means unknown, not "root"); it is read from the object's record and not
re-verified (use §3.4 for the verified chain). `signals` is diagnostic metadata about how
the result was reached; it is informational and its fields may change. A verification Mnemo could not complete is never
a `200`: it is `503 {"code": "verification_unavailable"}`, carries no result, costs nothing, and is retried (§6).

### 3.6 Promote — `POST /v1/agent/namespace/promote`

Optional and human-assisted; an autonomous agent never needs it. See §8.

### 3.7 Fund — `POST /v1/agent/namespace/fund`

Buys `burst_500` for the capability's own namespace. No body: nothing you send selects a price, a quantity, a duration
or a namespace. Without a payment the answer is the challenge: `402 {"code": "payment_required", "offer": {"id":
"burst_500", "price_usd": "5.00", "credits": 500, "funded_window_days": 14, "grace_hours": 24}, …}` with the Terms
fields, `Cache-Control: no-store`, x402 in `PAYMENT-REQUIRED` and one `WWW-Authenticate: Payment` per accepting MPP
method (`tempo`, `stripe`). Pay with **one** of them and send the request again with `PAYMENT-SIGNATURE` **or**
`Authorization: Payment` (both together: `400 payment_credential_conflict`). §5.3 walks through it.

`200`:

```json
{"offer": "burst_500", "credits_granted": 500, "funded_until": "2026-11-10T12:00:00+00:00"}
```

plus the rail's receipt (`PAYMENT-RESPONSE` for x402, `Payment-Receipt` for MPP) — on every `200` for that payment,
including a resend. `credits_granted` is the pack's size; a resent payment returns this same body and grants nothing
again (§6). `funded_until` is the namespace's current funded window (after a later refill, a resend of an older payment
shows the newer window). `retained_until` and the rest of the funded state are read with `GET /v1/agent/namespace`
(§3.2). On a deployment that does not sell bursts the route answers `404` for every method.

**Capacity.** A new burst is sold only while Mnemo can admit another funded namespace. When it cannot, the answer is
`503 {"code": "funded_capacity_unavailable", "retry_after_seconds": 300}` with `Retry-After: 300` and **no payment
challenge** — nothing is offered and nothing is charged. Retry later, or use `single_verify`. A refill of a namespace
that is already funded is never refused for capacity.

## 4. Namespace lifecycle

- **Lifetime** is fixed at creation: default 24 h, 60 s to 72 h. Activity does **not** extend it, and there is no
  renewal; only a funded namespace stays usable longer (§4.1).
- `expires_at` is returned at creation, on every embed (`namespace_expires_at`), and by the status call. On a funded
  namespace (§4.1) the status call keeps the original `expires_at` (its `seconds_remaining` counts to it), while embed's
  `namespace_expires_at` refers to `retained_until`; use `retained_seconds_remaining` there. Its one warning comes with
  the last 24 hours of retention (the grace), on the status call, with `expires_at` = `retained_until`.
- **One warning**: the first status or embed response after 75% of the lifetime has passed carries, once,
  `"warning": {"code": "EPHEMERAL_STORAGE_EXPIRING", "expires_at": "…", "seconds_remaining": …,
  "action_required": "upgrade_to_persistent", "data_after_expiry": "purged"}`. Mnemo never contacts the agent.
  `action_required` is advisory: nothing is required unless you want to keep the data, which needs a person to
  promote the namespace (§8).
- **At `expires_at`** the capability stops authenticating (`401`), embeds are refused (`410
  EPHEMERAL_NAMESPACE_EXPIRED`), and the namespace's data is purged. Nothing is kept for a namespace that was not
  promoted. A funded namespace follows §4.1 instead: it keeps working past `expires_at`.
- A paid verification needs at least **120 s** of lifetime left; closer to expiry it is refused (`402
  insufficient_credits`, no payment requested). Promotion needs at least **5 minutes** left.
- **Per namespace**: at most 10,000 objects and 26,214,400 accounted bytes (25 MiB). One object accounts for
  `4 × dimensions + 512` bytes, plus the size of its `subject`.

### 4.1 Funded namespaces (`burst_500`)

- **500 credits**, one per healthy verification, usable until **`funded_until`** = 14 days after the payment settled.
  Unused credits expire then.
- **Refill**: buying `burst_500` again gives a fresh 500 credits and a fresh 14-day window from that payment. Credits and
  time never stack: unused credits of the previous burst are replaced, not added.
- **Grace**: for 24 hours after `funded_until` verification is refused (`402 funded_window_ended`) and so are embeds
  (`410 EPHEMERAL_NAMESPACE_EXPIRED`). The namespace is not gone: its capability still authenticates, its data stays
  retained through **`retained_until`** (= `funded_until` + 24 h), and a refill reopens both verification and writes;
  promotion stays possible. Do not abandon it for a new namespace. After `retained_until` the capability answers `401` and
  the namespace is purged like any expired namespace.
- **Credits used up** inside the window: verify answers `402 funded_credits_exhausted`, with no payment challenge. Refill
  or promote; a funded namespace is never sold a single verification.
- **Storage**: a hard allowance of 100,000,000 bytes per funded namespace; the 10,000-object limit still applies. Either
  limit answers `413 funded_storage_quota_exceeded` (`limit`: `bytes` or `objects`, with `retained_until`). A funded
  namespace accounts everything an object stores: `4 × dimensions + 512` bytes, its `subject`, every stored copy of
  `model_id`, `model_version` and `request_id`, 1,024 bytes when it has a `subject`, and 512 bytes for a `parent`
  link. A refill buys verifications and a new window, not more
  storage. While a burst purchase for the namespace is being completed, an embed can answer `409 funded_sale_pending`
  (`Retry-After: 30`): retry the write.
- **When**: buy at least 15 minutes before the namespace stops being usable — `expires_at` for an unfunded namespace,
  `retained_until` for a funded one (a refill) — otherwise `409 namespace_expiring`. A refill is therefore possible
  through the grace until 15 minutes before `retained_until`. Only an `ACTIVE` namespace can be funded (`409
  namespace_not_fundable`).
- `funded_until` is returned by the `200` of §3.7; `funded_until`, `retained_until` and `retained_seconds_remaining` by
  §3.2; `funded_until` (with `retained_until` when credits ran out) by the two funded `402`s; and `retained_until` by
  the funded `413`.
- No automatic refunds or clawbacks. A paid burst is final; a service failure is reviewed manually.

## 5. Paying

Every accountless `402` that asks for payment carries the challenge of **each rail that is accepting payments** for that
offer. Pay with exactly one of them. No rail is required:

| Rail | Challenge header | You send | Receipt on the `200` | Offers |
|---|---|---|---|---|
| x402 (USDC on Base) | `PAYMENT-REQUIRED` | `PAYMENT-SIGNATURE` | `PAYMENT-RESPONSE` | `single_verify`, `burst_500` |
| MPP Tempo (USDC.e on Tempo) | `WWW-Authenticate: Payment … method="tempo"` | `Authorization: Payment <credential>` | `Payment-Receipt` | `single_verify`, `burst_500` |
| MPP card (Stripe Shared Payment Token) | `WWW-Authenticate: Payment … method="stripe"` | `Authorization: Payment <credential>` | `Payment-Receipt` | `burst_500` only |

### 5.1 x402

Mnemo implements x402 V2 (`exact` scheme, EVM, EIP-3009 `transferWithAuthorization`, settlement **before** the
verification). Any standard x402 V2 client can pay. The steps below use `/v1/verify`; for `burst_500` the same steps
apply to `POST /v1/agent/namespace/fund` with `amount` `5000000` (§5.3).

**Terms notice.** The payment challenge identifies the Terms of Service before you pay. Its JSON body states them next
to the `code`:

```json
{"code": "insufficient_credits", "terms_url": "https://www.trymnemo.com/terms", "terms_version": "2026-10-12",
 "privacy_url": "https://www.trymnemo.com/privacy", "dpa_url": "https://www.trymnemo.com/dpa"}
```

Every accountless `402`, and the `201` of `POST /v1/agent/namespaces`, carries the header
`Link: <https://www.trymnemo.com/terms>; rel="terms-of-service", <https://www.trymnemo.com/privacy>; rel="privacy-policy"`.
The Terms are not part of `PAYMENT-REQUIRED`, which is unchanged: sign exactly what it states (step 3). Sending a
payment authorization in response to the challenge accepts the Terms in the stated `terms_version` (Terms 5.2). Only
the challenge carries the `terms_*` fields, so test `code` rather than the whole body. A call with an API key never
gets a challenge: when its plan is used up, verify answers `402 {"code": "insufficient_credits"}` with no
`PAYMENT-REQUIRED` and no `terms_*` fields (§1).

1. `POST /v1/verify` with the capability and your body. With no paid credit the answer is the challenge: `402` with
   `"code": "insufficient_credits"` (and the Terms fields above) and a **`PAYMENT-REQUIRED`** header: base64-encoded
   JSON.
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
`expires_at` (§4); it does not move to another namespace. A credit is non-transferable, cannot be redeemed for
money, USDC or any other asset, has no monetary value, and expires with the namespace.

Mnemo never asks a namespace that already has a paid credit to pay again, and a payment is never accepted for a
different amount, asset, network or recipient.

### 5.2 MPP (Tempo, card)

Mnemo implements the HTTP `Payment` authentication scheme of the Machine Payments Protocol
([mpp.dev](https://mpp.dev)) with the `charge` intent. Any standard MPP client can pay (for example `mppx` or `pympp`).

1. The `402` carries one `WWW-Authenticate: Payment id="…", realm="api.trymnemo.com", method="…", intent="charge",
   request="…", expires="…", opaque="…"` per accepting MPP method. `request` is base64url JSON:
   - **`method="tempo"`**: `{"amount": "10000" | "5000000", "currency": "0x20c0…8b50", "recipient": "0x…",
     "methodDetails": {"chainId": 4217}}` — a `transferWithMemo` of exactly `amount` of the USDC.e `currency` to
     `recipient` on Tempo mainnet, **whose memo is the MPP attribution memo bound to this challenge** (derived from the
     realm and the challenge `id`). The memo is not a field of the challenge: standard MPP clients (`mppx`, `pympp`)
     derive it. **Do not build a Tempo transfer by hand.** A transfer that pays the right amount to the right recipient
     but whose memo does not name this challenge is not this payment: it is refused and not credited, and Mnemo makes no
     automatic refunds. Take every value from the challenge; do not hard-code them.
   - **`method="stripe"`** (`burst_500` only): `{"amount": "500", "currency": "usd", "methodDetails": {"networkId":
     "profile_…", "paymentMethodTypes": ["card"]}}` — your agent platform grants Mnemo's Stripe profile (`networkId`) a
     Shared Payment Token for exactly 5.00 USD. Mnemo never receives card data.
2. Pay with your MPP client against that challenge and send the **same request again** with `Authorization: Payment
   <credential>`. A Tempo credential may carry the signed transaction (Mnemo broadcasts it unchanged) or the hash of a
   transaction you already sent; a card credential carries the Shared Payment Token. A signed transaction needs a
   secp256k1 key, an expiring nonce and no fee-payer signature, and must be valid for at most 300 s and no later than the
   challenge's `expires` (standard clients do this); a wallet with another key type (passkey/WebAuthn) pays and sends the
   transaction hash instead. A hash is accepted once the transaction is final; until then the answer is `503
   payment_processing` or `payment_unavailable`: resend the same credential.
3. The `200` carries `Payment-Receipt` (base64url JSON: `method`, `reference` — the transaction hash or the Stripe
   PaymentIntent — `status`, `timestamp`). A challenge is bound to this namespace and offer: one for another namespace,
   another offer or another route is refused (`402` with `type` `…/invalid-challenge` or `…/method-unsupported`, and a
   fresh challenge). An MPP refusal adds RFC 9457 `type`, `title` and `status` members to Mnemo's body (on the fund
   route also `detail`, a refusal category); decide on `code` and `type`. A refused credential bought nothing, and resending it cannot
   succeed; paying the fresh challenge is a new payment.

One Tempo transaction pays exactly one challenge, and one Shared Payment Token is one payment. MPP challenges carry no
Terms fields themselves; the `402` body that carries them states the Terms exactly as for x402.

### 5.3 Paying for `burst_500`

1. `POST /v1/agent/namespace/fund` with the capability and no body → `402 payment_required` with the offer and the
   challenge of each accepting rail (§3.7). `503 funded_capacity_unavailable` means no burst can be sold right now:
   nothing is offered or charged.
2. Pay one challenge: x402 (`amount` `5000000`, §5.1), MPP Tempo (`amount` `5000000`) or MPP card (`amount` `500` USD
   cents).
3. Send `POST /v1/agent/namespace/fund` again with `PAYMENT-SIGNATURE` **or** `Authorization: Payment` → `200 {"offer":
   "burst_500", "credits_granted": 500, "funded_until": …}`. From now on `POST /v1/verify` spends the burst credits
   without asking for payment.

## 6. Retries and idempotency

For a paid verify the payment identifies the operation. The simplest correct client builds **one body per
verification, without `request_id`**, and resends that identical body with the same `PAYMENT-SIGNATURE` in every case
below. With MPP the same rules hold for the same `Authorization: Payment` credential: wherever this table says
`PAYMENT-SIGNATURE`, an MPP payer resends its credential unchanged.

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
| A completed paid verify sent again (identical body, same payment) | you get the stored result (`200`), without a receipt header; nothing runs or settles again | once |
| `POST /v1/agent/namespace/fund`: no response, or `503 payment_processing` / `503 payment_unavailable` (`Retry-After: 30`) after you paid | resend the same request with the **same** payment (`PAYMENT-SIGNATURE` or `Authorization: Payment`) after `Retry-After`. Never pay again: while a burst payment is being confirmed, the route offers no new challenge | once |
| `POST /v1/agent/namespace/fund`: the same payment sent again after a `200` | `200` with the identical body (`offer`, `credits_granted`, `funded_until`) and receipt; no second grant, no new window | once |
| `503 funded_capacity_unavailable` | no burst can be sold now and no challenge was offered; nothing was charged. Retry after `Retry-After` (300 s), or buy `single_verify` | — |
| MPP: `503 payment_processing` (`Retry-After: 30`) on `/v1/verify` | your MPP payment is not final or could not be confirmed yet. Resend the identical body with the same `Authorization: Payment` credential after `Retry-After`; never pay again | once |
| MPP: `402` with a fresh `WWW-Authenticate` challenge and a problem `type` after you sent a credential | that credential was refused and bought nothing; resending it cannot succeed. Paying the fresh challenge is a new, deliberate payment | — |

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
`complete: true` means the walk reached the root; `depth` is the number of ancestors returned. A broken chain is never
complete. A `200` with `complete: false` carries `truncated: true`: the read stopped at the depth limit. Lineage records
the parents you named and Mnemo verified at embed time; it does not describe what the transformation did.

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
   `expires_at` (a funded namespace: `retained_until`, §4.1) the capability no longer authenticates (`401`) and the
   namespace cannot be promoted.

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
  the data is purged at `expires_at` (a funded namespace: `retained_until`) like any namespace.
- `state` `PROMOTING`: the promotion had started, and Mnemo completes it — through a prompt repeat by the same person,
  or in the background. A repeat that completes issues a fresh credential and revokes any earlier one. A background
  completion issues no credential through this API; afterwards the capability answers `401` and the data is kept.
- `state` `PERSISTENT`: the promotion completed but its response was lost. The same person repeats the call promptly
  to receive a fresh credential (any earlier one is revoked).
- `401`: the capability no longer authenticates. Either the promotion was completed (data kept) or the namespace
  expired before promotion began (data purged); this API does not tell the two apart.

Promotion is free. It does not start the free trial and includes no verifications: the issued API key uses the
account's subscription plan ([pricing](https://www.trymnemo.com/pricing)), and until the account has one its calls can
be refused with `402 {"code": "insufficient_credits"}`, without `PAYMENT-REQUIRED` (§1). The promotion response's
`tier` and `retention_seconds` state the plan and retention the account starts with.

Promotion does not mean indefinite retention: the account's objects follow the retention of its plan (§9).

## 9. Retention

An object stays verifiable for its plan's retention, counted from when it was stored — for a promoted namespace, from
promotion:

| Plan | Retention |
|---|---|
| Free trial | until the trial ends (at most 30 days) |
| Starter | 90 days |
| Growth | 365 days |
| Scale | 1,095 days |
| Pro (legacy) | 365 days |
| Enterprise | indefinite |

A promoted account without a plan keeps objects for the `retention_seconds` stated in the promotion response (§8).
Upgrading later does not extend the retention of objects already stored. After an object's retention ends, verifying it
returns `verified: false` (a healthy negative result). Its lineage records may remain readable, but that is not
guaranteed. An ephemeral namespace that is not promoted keeps nothing after `expires_at` (a funded namespace: after
`retained_until`, §4.1).

## 10. Limits

| Limit | Value | When exceeded |
|---|---|---|
| Requests per namespace (all capability calls together) | 120 per minute | `429`, `Retry-After: 60` |
| Namespace creation requests per source address | 5 per clock hour; every well-formed request that reaches the limit counts, including ones then refused with `429` or `503` | `429`, `Retry-After: 3600` |
| Objects per namespace | 10,000 | `413 NAMESPACE_OBJECT_LIMIT` |
| Accounted bytes per namespace | 25 MiB (26,214,400); a funded namespace 100,000,000 | `413 NAMESPACE_BYTE_LIMIT`; funded: `413 funded_storage_quota_exceeded` |
| Namespace lifetime | 60 s – 72 h, default 24 h | `400 EPHEMERAL_LIFETIME_UNSUPPORTED` |
| Vector dimensions | 512 – 4096 | `400 vector_dimension_unsupported` |
| Request body | 256 KiB (embed with a capability); 4 KiB (namespace creation) | `413 REQUEST_BODY_TOO_LARGE` |
| Lineage depth | 64 | `409 LINEAGE_DEPTH_EXCEEDED` |

Mnemo also protects shared capacity: when it is temporarily full, creation answers `503 EPHEMERAL_CAPACITY_EXHAUSTED`
and an embed can answer `413 GLOBAL_BYTE_LIMIT`. Retry later, backing off for minutes rather than seconds: each
creation retry may use one of the 5 hourly creation requests. New bursts are sold only while funded capacity is left
(`503 funded_capacity_unavailable`, before any payment, §3.7); a namespace that is already funded keeps writing up to its
own 100,000,000 bytes.

## 11. Errors

Most errors are `{"detail": …}` (a string, or an object with a `code`). Billing refusals on verify, the funded verify
refusals, and the payment answers of `POST /v1/agent/namespace/fund` (`402`, `409`, and the `503`s
`payment_processing`, `payment_unavailable`, `funded_capacity_unavailable`, `funding_unavailable`) are a bare
`{"code": …}`; the fund route's `400` and `403`, and an infrastructure `503`, are `{"detail": {"code": …}}`. Decide on
the status and the `code`, wherever it is.

| Status | Meaning | What to do |
|---|---|---|
| `400` | malformed input: `vector_dimension_unsupported`, `vector_nonfinite`, `vector_magnitude_extreme`, `vector_zero_norm`, `vector_near_constant`, `idempotency_key_invalid`, `EPHEMERAL_LIFETIME_UNSUPPORTED`; on verify and fund, `payment_credential_conflict` (x402 and MPP together) | fix the request |
| `401` | invalid or expired capability (unknown, revoked by a completed promotion, or past `expires_at` — a funded namespace: past `retained_until`); invalid API key; on promotion, also a missing capability (`CAPABILITY_REQUIRED`) or a missing human session | a namespace past `expires_at` (funded: `retained_until`) cannot be used; create a new one. After a promotion attempt, see §8 |
| `402` | `insufficient_credits` with `PAYMENT-REQUIRED` and/or `WWW-Authenticate: Payment`: pay (§5). Bare `{"code": "insufficient_credits"}` without a challenge after you sent a payment: this request was not funded (§5, §6). `{"detail": {"code": "insufficient_credits", …}}`: too close to expiry to pay. `ACCOUNTLESS_VERIFY_NOT_ENABLED`: paid verification is not enabled. Fund: `payment_required` (the burst challenge; a refused payment adds a `reason` category or an MPP `type`). Funded namespace: `funded_window_ended` (grace), `funded_credits_exhausted` (credits used) — refill or promote | pay, resend with the same payment, refill, or create a new namespace |
| `403` | no credential at all (`Authentication required`); the capability may not call this path; `LINEAGE_PARENT_NOT_VERIFIED`; promotion by someone other than the person who started it | send the capability in `X-Mnemo-Capability` |
| `404` | accountless access not enabled; `LINEAGE_NOT_FOUND`; on `POST /v1/agent/namespace/fund`, bursts are not sold on this deployment | — |
| `409` | `Duplicate request_id`, `idempotency_key_reused`, `request_in_progress`, `PAYMENT_UNRECOVERABLE_PAYLOAD_PURGED`, a broken lineage chain, `TOO_LATE_TO_PROMOTE`, `PROMOTION_IN_PROGRESS`, `EPHEMERAL_NAMESPACE_PROMOTING`; on fund, `namespace_expiring`, `namespace_not_fundable`; on embed, `funded_sale_pending` (retry after `Retry-After`) | see §4.1, §6–§8 |
| `410` | `EPHEMERAL_NAMESPACE_EXPIRED`; `SOURCE_EXPIRED` / `SOURCE_GONE` (a promotion call that raced the namespace's expiry) | create a new namespace — unless the namespace is funded and in its grace (`GET /v1/agent/namespace` still answers, with `retained_until` in the future): then refill or promote it instead (§4.1) |
| `413` | a namespace limit (`funded_storage_quota_exceeded` on a funded namespace) or the body size limit | — |
| `422` | the body has unknown or mistyped fields | fix the request |
| `429` | rate limit | wait `Retry-After` seconds |
| `503` | `verification_unavailable` (not charged — retry, §6), `billing_unavailable`, `EPHEMERAL_CAPACITY_EXHAUSTED`, `EPHEMERAL_INFRASTRUCTURE_UNAVAILABLE`, `LINEAGE_UNAVAILABLE`; payment: `payment_processing`, `payment_unavailable` (resend the same payment, §6); fund: `funded_capacity_unavailable` (no challenge, nothing charged), `funding_unavailable` | retry with backoff; never pay twice |

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
#    (or pay the MPP challenge and resend with "Authorization: Payment <credential>" → 200 + Payment-Receipt)
curl -s -i -X POST $API/v1/verify -H "X-Mnemo-Capability: $CAP" -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE" \
  -H 'Content-Type: application/json' -d '{"vector": [ …the same watermarked vector… ]}'

# optional: buy burst_500 (500 verifications, 14 days) → 402 with every rail's challenge; pay one, resend
curl -s -i -X POST $API/v1/agent/namespace/fund -H "X-Mnemo-Capability: $CAP"
```

## 13. Not in v1

- **MCP**: MCP support is planned; there is no public MCP server today. Use the HTTP API.
- Renewing or extending an unfunded ephemeral namespace (a burst keeps a namespace usable for its funded window,
  §4.1; to keep data permanently, a signed-in person can promote it, §8).
- Notifications, webhooks or callbacks — Mnemo never contacts an agent.
- Payment assets and methods other than USDC on Base (x402 `exact` with EIP-3009), USDC.e on Tempo (MPP), and a card
  through a Stripe Shared Payment Token (MPP, `burst_500` only).
