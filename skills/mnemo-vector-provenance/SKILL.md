---
name: mnemo-vector-provenance
description: Watermark embedding vectors with Mnemo and later verify whether a vector you hold resolves to an object registered to your own Mnemo namespace or account, plus record and read verified parent-to-child lineage. Use when an agent stores embeddings and must check, before using them, that retrieved vectors (for example RAG chunks from a vector database) resolve to its own registered objects, when it needs to record that one embedding was derived from another (chunk, summary, translation, re-embed), or when the user mentions Mnemo or trymnemo.com. No account needed. Namespace, embed and lineage are free; verify is paid at its HTTP 402 challenge ($0.01 per call over x402 or MPP on Tempo) or in advance with a $5 500-verification burst bought at POST /v1/agent/namespace/fund (x402, MPP on Tempo, or card via Stripe SPT). Not for similarity search, generating embeddings, judging truth, authorship or ownership, text, file or image authenticity, or checking another party's vectors.
---

# Mnemo: embedding-vector provenance

- API base: `https://api.trymnemo.com`
- Full contract (source of truth): https://www.trymnemo.com/agent-protocol.md
- OpenAPI 3.1: https://www.trymnemo.com/openapi.json
- Runnable examples: https://www.trymnemo.com/examples/agent-quickstart.sh and https://www.trymnemo.com/examples/agent_quickstart.py

`payment_menu` in `GET /v1/agent/namespace` is authoritative for what you can buy right now and over which rails. Each live `402` challenge is authoritative for amount, asset and recipient. Where either differs from this file or the docs, follow them.

## When to use it

- You embedded vectors through Mnemo and need to check whether a vector you hold now (for example one retrieved from a vector store) resolves to one of your own registered objects before you use it.
- You need a verified record that one of your objects was derived from another of your objects.

## When not to use it

- Vectors never embedded through Mnemo in your namespace or account. There is no retroactive coverage.
- Checking whether a vector belongs to someone else. Verify only resolves your own objects.
- Similarity search, vector storage, or generating embeddings. Mnemo does none of these.
- Raw text, images, audio, video, or file authenticity. Mnemo works on embedding vectors only.
- Personal data subject to EEA, UK or Swiss data protection law on the accountless path.

## Workflow (no account, no human)

1. **Create a namespace** (free, no auth): `POST /v1/agent/namespaces` with JSON body `{}`.
   - Store `capability` (returned once) and `expires_at`. The default lifetime is 24 h and the maximum 72 h; activity does not extend it.
   - Send the capability as `X-Mnemo-Capability` on every later call.
2. **Embed** (free): `POST /v1/embed` with `{"vector": [...], "model_id": "<label>"}`.
   - `vector`: 512 to 4096 finite FP32 numbers, unit-norm expected. You supply it; Mnemo does not compute embeddings.
   - `model_id`: a label you declare (for example `text-embedding-3-small`).
   - Store the returned `watermarked_vector` and `vector_uid`. Use the watermarked copy in place of your original; it is the vector that verifies.
   - Optional lineage: add `"parent": {"vector_uid": "...", "relation": "summary", "vector": [...]}`.
     - `relation` is one of `re_embed`, `summary`, `chunk`, `translation`, `transform`.
     - `vector` is the parent's watermarked vector.
     - A parent that does not verify as yours returns `403 LINEAGE_PARENT_NOT_VERIFIED`.
3. **Verify** (paid): `POST /v1/verify` with `{"vector": [...]}`. Without credit, the call returns `402`; pay and resend the identical body (see Payment).
4. **Lineage** (free): `GET /v1/lineage/{vector_uid}` returns the verified chain, parent first. Every link is re-verified on every read; `409` means a link no longer verifies.

## Reading a verify result

- Decide on `verified`. `confidence` is diagnostic, not a probability. `policy_ok` is not the verdict.
- `verified: true`: `vector_uid` is the object of yours it resolved to.
- `verified: false` with `vector_uid: null`: a healthy, charged, final result.
  - Attribution to your namespace could not be shown. It is not proof the vector belongs to someone else.
  - Do not pay again hoping for a different answer.
- `503 verification_unavailable`: not a result and not charged. Resend the identical body with the same payment credential.

## Payment

Only verify consumes credits, one per healthy verification, positive or negative. A burst is bought at `POST /v1/agent/namespace/fund` for $5.00. These are free:
- namespace creation and status;
- embed and lineage;
- promotion;
- refused or malformed requests;
- `503`s.

### Offers

| Offer | Price | You get | Where you buy it | Rails |
|---|---|---|---|---|
| `single_verify` | $0.01 | 1 verification | the `402` of `POST /v1/verify` | x402 (USDC on Base, `eip155:8453`); MPP on Tempo (USDC.e, chain 4217) |
| `burst_500` | $5.00 | 500 verifications in a 14-day funded window, 100 MB storage | `POST /v1/agent/namespace/fund` | x402 (Base); MPP on Tempo; MPP card via Stripe Shared Payment Token (SPT) |

- **No rail is required.** Pay with whichever rail your wallet supports.
- **Card is only for `burst_500`.** Card (SPT) is never offered for `single_verify`: Stripe's minimum card charge rules out $0.01.
- **Discovery.** `GET /v1/agent/namespace` returns `payment_menu`: each offer this namespace can buy now (`id`, `price_usd`, `credits`, `route`, `rails`).
  - An offer or rail that is not listed cannot be bought right now.
  - A listed `burst_500` can still be answered `503 funded_capacity_unavailable` or `503 payment_processing` (see below).
- **Which offer.** Pick `single_verify` for a few one-off checks. Pick `burst_500` when:
  - you expect many verifications within 14 days;
  - the namespace needs to outlive 72 h;
  - you can only pay by card.
- **Funded namespaces cannot buy singles.** A funded namespace is never sold `single_verify`; it refills with another `burst_500`.

### Paying the 402

Read the `402` and pay exactly one of the challenges it carries. Take recipient, amount and asset from the challenge; never hard-code them.

**Rails:**
- **x402** (header `PAYMENT-REQUIRED`): x402 V2, scheme `exact`, USDC on Base, EIP-3009.
  - Pay, then resend the same request with `PAYMENT-SIGNATURE`.
  - A `200` on which payment settled carries `PAYMENT-RESPONSE`.
- **MPP** (header `WWW-Authenticate: Payment`, one per method): `method="tempo"` (USDC.e on chain 4217) for either offer; `method="stripe"` (card via SPT) for `burst_500` only.
  - Pay with a standard MPP client (`mppx`, `pympp`), then resend the same request with `Authorization: Payment <credential>`.
  - The receipt comes back in `Payment-Receipt`.
  - **Never build a Tempo transfer by hand.** It must carry the MPP attribution memo bound to the challenge. A transfer to the right recipient for the right amount but without that memo is not credited, and there are no automatic refunds.
  - A Tempo wallet with a passkey/WebAuthn key pays first and sends the transaction hash instead of a signed transaction.
- A `402` may carry only some rails' challenges: use whichever is present.

**Single verification:**
- Leave `request_id` out of a paid verify. The payment identifies the operation, so every retry resends the identical body.

**Burst** (`POST /v1/agent/namespace/fund`, capability, no body):
1. Without payment you get `402 {"code": "payment_required", "offer": {"id": "burst_500", ...}}` with every accepting rail's challenge:
   - x402 and Tempo amount `5000000`;
   - card amount `500` US cents.
2. Pay one and resend with `PAYMENT-SIGNATURE` **or** `Authorization: Payment` (both together: `400 payment_credential_conflict`).
3. The answer is `200 {"offer": "burst_500", "credits_granted": 500, "funded_until": "..."}` with the rail's receipt. From then on `POST /v1/verify` spends burst credits without asking for payment.

### Never pay twice

- **`402` without a challenge header after you paid with x402.** This request was not funded yet (refused, or settlement not final).
  - Resend the identical body with the same `PAYMENT-SIGNATURE`, with backoff.
  - Stop 90 minutes after its `validBefore`.
  - A first payment that settles late becomes a credit that the next verify in this namespace (sent without a payment header) uses.
- **`409 request_in_progress`.** Wait, then resend the identical body with the same payment credential.
- **Resending a payment is safe on every rail.** The same `PAYMENT-SIGNATURE` or `Authorization: Payment` credential sent again never creates a second charge or credit:
  - A completed paid verify sent again returns its stored result (`200`, without a receipt header).
  - On `POST /v1/agent/namespace/fund` the same payment sent again returns the same `200` body (`credits_granted` is the pack size, 500) and grants nothing again.
- **`503 payment_processing`** (on `/v1/verify` or `/fund`) **or `503 payment_unavailable`** (on `/fund`), with `Retry-After: 30`. The payment is being confirmed. Resend the same request with the same credential after `Retry-After`; never pay again. While a burst payment is being confirmed, `/fund` offers no new challenge.
- **MPP `402` with a fresh `WWW-Authenticate` challenge and a problem `type`** after you sent a credential. That credential was refused and bought nothing; resending it cannot succeed. Paying the fresh challenge is a new, deliberate payment.
- **The namespace expired after your payment was accepted.** Within one hour, resend with the same capability and payment the body exactly as first sent. Never pay again in a new namespace: a credit never moves to another namespace.
- **Near expiry.** A paid verify needs at least 120 s of namespace life left; closer to expiry it is refused without a challenge.
- **`409 idempotency_key_reused`.** That payment already bought a verification of a different vector. Request again without payment.
- **Any rail: never create a second payment automatically.**
  - After a timeout, a `503`, or an unclear result, resend with the same credential, or check `GET /v1/agent/namespace`.
  - Only pay again if a new `402` challenge asks for it.

## Funded namespaces (`burst_500`)

- **Credits.** 500 credits, usable until `funded_until`: 14 days after the payment settled. Unused credits expire then.
- **Refill.** Buying `burst_500` again gives a fresh 500 and a fresh 14-day window; credits and time do not stack.
- **Grace.** For 24 hours after `funded_until`, verify answers `402 funded_window_ended` (no challenge) and embed answers `410 EPHEMERAL_NAMESPACE_EXPIRED`.
  - The namespace is **not** gone: the capability still works and data is kept through `retained_until` (= `funded_until` + 24 h).
  - Refill to reopen verify and embed, or let it lapse. Do not abandon it for a new namespace.
  - After `retained_until` the capability answers `401` and the namespace is eligible for purge.
- **Credits used up inside the window.** Verify answers `402 funded_credits_exhausted` (no challenge). Refill with another `burst_500`.
- **Storage.** A hard cap of 100,000,000 bytes per funded namespace; the 10,000-object limit still applies. Either limit answers `413 funded_storage_quota_exceeded`. A refill adds verifications, not storage.
- **Sale in progress.** While a burst purchase is completing, an embed can answer `409 funded_sale_pending` (`Retry-After: 30`); retry the write.
- **No capacity for a new burst.** `/fund` answers `503 {"code": "funded_capacity_unavailable", "retry_after_seconds": 300}` with `Retry-After: 300` and **no payment challenge**.
  - Nothing was offered or charged; do not pay.
  - Retry later, or fall back to `single_verify`.
  - A refill of an already-funded namespace is never refused for capacity.
- **Timing.**
  - Buy a burst at least 15 minutes before the namespace stops being usable (otherwise `409 namespace_expiring`). That is `expires_at` for an unfunded namespace and `retained_until` for a refill.
  - On a funded namespace, `expires_at` and `seconds_remaining` in the status keep counting to the original expiry. Use `retained_until` and `retained_seconds_remaining` instead.
  - Plan verifications to finish before `funded_until`.
- **Where the timestamps are.**
  - `funded_until` is in the `/fund` `200`: the namespace's current window. After a later refill, a resend of an older payment shows the newer window.
  - `funded_until`, `retained_until` and `retained_seconds_remaining` are in `GET /v1/agent/namespace`.
  - `funded_until` is also in the two funded `402`s; `funded_credits_exhausted` also carries `retained_until`, and so does the funded `413`.
- **No automatic refunds or clawbacks.**

## Errors

- `401`: invalid or expired capability.
- `410 EPHEMERAL_NAMESPACE_EXPIRED`: the namespace and its data are gone; create a new one.
  - Exception: a funded namespace in its grace answers `410` to embeds while `GET /v1/agent/namespace` still answers. Refill or promote it instead.
- `403` with no credential: send `X-Mnemo-Capability`.
- `400 vector_dimension_unsupported`: send 512 to 4096 dimensions.
- `429`: wait `Retry-After`. Limits are 120 requests per minute per namespace and 5 namespace creations per clock hour per source.
- `404` on namespace creation: accountless access is not enabled on this deployment. `404` on `/fund`: bursts are not sold on this deployment.

## Limits

- Unfunded namespace: 10,000 objects, 25 MiB of accounted bytes, lifetime 60 s to 72 h fixed at creation.
- Funded namespace (`burst_500`): 10,000 objects and 100,000,000 bytes. Verify and embed until `funded_until`; data kept, and refill or promotion possible, until `retained_until`.

## Keeping data permanently (optional, needs a person)

Autonomous agents never need this.

- A person signed in at https://www.trymnemo.com/login (email session required) can promote the namespace to a permanent account.
- Promotion is `POST /v1/agent/namespace/promote`, sent with both the capability and that person's session token.
- Ids and lineage are preserved.
- Account API keys (`X-API-Key`) use the account's subscription plan and are never offered a payment challenge.

## Terms

Calling the API through an agent is use of the Services by whoever operates that agent and acceptance of the Mnemo Terms of Service: https://www.trymnemo.com/terms
