# Mnemo Agent API — public protocol

**Mnemo (trymnemo.com) watermarks embedding vectors and checks whether a vector was issued to your own account or namespace. This repository is the public HTTP contract for its accountless Agent API at `https://api.trymnemo.com`.**

**Provenance, not proximity.** In Mnemo, provenance means a vector resolves to a `vector_uid` that Mnemo issued at embed time and that is still attributable to the account or namespace that issued it. A nearest-neighbour search can say a vector is close to something, not whether a vector you hold was issued by your own pipeline. Use Mnemo when you store embeddings and later need to check whether a vector you hold (for example a retrieved one) was issued to your own namespace or account, or to record and read a verified parent-to-child derivation.

## What this repository is

The public contract for the **accountless Mnemo Agent API**. An agent with no account and no person in the loop:

1. **Namespace** — `POST /v1/agent/namespaces` creates a short-lived namespace (default 24 h, at most 72 h) and returns a capability once; send it as `X-Mnemo-Capability`.
2. **Embed** — `POST /v1/embed` with your `vector` and a `model_id` (both required; `model_id` is a label you declare) returns a measurably perturbed watermarked copy of your vector and a `vector_uid`. Free.
3. **Lineage** — `GET /v1/lineage/{vector_uid}` returns the chain of parents you named with `parent` at embed time, each verified as yours; it does not check what the transformation did. Free.
4. **Verify (paid)** — `POST /v1/verify` answers `402` with its payment challenges: x402 (`PAYMENT-REQUIRED`, USDC on Base) and MPP on Tempo (`WWW-Authenticate: Payment`, USDC.e). Pay one and resend the identical body with `PAYMENT-SIGNATURE` or `Authorization: Payment`. The result carries `verified`, `confidence`, `vector_uid` (null when not verified) and `policy_ok`; decide on `verified`. Each healthy verification, positive or negative, costs 0.01 USD (see §1 of [`agent-protocol.md`](agent-protocol.md)).
5. **Burst (optional)** — `POST /v1/agent/namespace/fund` sells 500 verifications for 5.00 USD, usable for 14 days, with a 100,000,000-byte storage allowance; pay over x402, MPP on Tempo, or a card through MPP and a Stripe Shared Payment Token. A card is never offered for a single verification, and no rail is required.

`GET /v1/agent/namespace` returns `payment_menu`: the offers and rails a namespace can buy right now. It is the authoritative discovery surface; each `402` challenge is authoritative for amount, asset and recipient.

**Scope of verify.** Mnemo Verify checks whether a submitted vector resolves to an object registered to the caller's Mnemo account or namespace. `verified: false` is a normal, charged result; it is not a statement about who else may have registered the vector.

`agent-protocol.md` is the reference for request/response details and pricing when anything here differs.

## Have an account API key? Use the Python SDK instead

Account holders call the same API with `X-API-Key` under their subscription plan (never machine payments). Use the official Python SDK:

```bash
pip install mnemo-protocol
```

```python
from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")
```

- SDK repository: https://github.com/MnemoProtocol/mnemo-sdk
- PyPI: https://pypi.org/project/mnemo-protocol/ (distribution `mnemo-protocol`, import `mnemo_sdk`)

The SDK does not implement accountless namespaces, lineage or machine payments (x402, MPP); for those, use this contract over HTTP.

Mnemo here is the embedding-vector provenance API at trymnemo.com (GitHub MnemoProtocol; PyPI mnemo-protocol, imported as mnemo_sdk). It is not the unrelated PyPI packages mnemo, mnemo-sdk, mnemo-ai or mnemo-mcp, and not an AI-memory app or MCP server.

## Contract files

| File | In this repo | On trymnemo.com | Contents |
|---|---|---|---|
| `agent-protocol.md` | [agent-protocol.md](agent-protocol.md) | https://www.trymnemo.com/agent-protocol.md | the complete contract: auth, lifecycle, pricing, x402 and MPP payment, bursts, retries, lineage, promotion, retention, limits, errors |
| `openapi.json` | [openapi.json](openapi.json) | https://www.trymnemo.com/openapi.json | OpenAPI 3.1 for the seven agent operations |
| `llms.txt` | [llms.txt](llms.txt) | https://www.trymnemo.com/llms.txt | discovery summary for agents |
| `agent-manifest.json` | [agent-manifest.json](agent-manifest.json) | https://www.trymnemo.com/agent-manifest.json | machine-readable manifest |
| `examples/agent-quickstart.sh` | [examples/agent-quickstart.sh](examples/agent-quickstart.sh) | https://www.trymnemo.com/examples/agent-quickstart.sh | end-to-end walkthrough with curl (placeholders only) |
| `examples/agent_quickstart.py` | [examples/agent_quickstart.py](examples/agent_quickstart.py) | https://www.trymnemo.com/examples/agent_quickstart.py | the same in Python, including the paid verify (placeholders only) |

Paying with `examples/agent_quickstart.py` needs Python 3.10+ (`pip install "x402[evm]==2.22.0"`); steps without payment need only the standard library. The examples pay with x402; MPP payments (Tempo, or a card for the burst) are made the same way with an MPP client.

An installable agent skill is published at https://www.trymnemo.com/.well-known/skills/mnemo-vector-provenance/SKILL.md (`npx skills add https://www.trymnemo.com`).

## When not to use Mnemo

- To establish truth, authorship, ownership or authenticity of content: Mnemo does not determine any of these.
- To check whether a vector belongs to someone else: verify only resolves objects registered to your own account or namespace.
- For vectors never embedded through Mnemo: there is no retroactive coverage.
- For similarity search or storage: Mnemo is not a vector database.
- To keep data in an accountless namespace past `expires_at`: it is purged unless a person promotes it.
- For raw text, images, audio or video: Mnemo works on embedding vectors (512–4096 numbers).
- When your pipeline must keep the original vector bit-for-bit: embed returns a perturbed copy that you store in its place.
- Through MCP: there is no public MCP server; use the HTTP API.
- On the accountless path (any payment rail), for personal data subject to EEA, UK or Swiss data protection law (see the DPA note in [`llms.txt`](llms.txt)).

## Legal

Access to or use of the Mnemo API through an automated agent, application, script, SDK, protocol client, wallet, autonomous system, or other automated means constitutes access to and use of the Services by the person or entity that operates, controls, authorizes, deploys, or causes that system to access the Services, and acceptance of the Mnemo Terms of Service (Terms 1.2 and 1.5). [Terms of Service](https://www.trymnemo.com/terms) · [Privacy Policy](https://www.trymnemo.com/privacy) · [Pricing](https://www.trymnemo.com/pricing) · Security reports: security@trymnemo.com (see [SECURITY.md](SECURITY.md)).

Copyright © Mnemo LLC. All rights reserved. Patent pending. Viewing this repository does not grant a license; rights are granted only as expressly stated in the applicable license and Terms of Service.
