# Mnemo Agent API — public protocol

**Mnemo (trymnemo.com) watermarks embedding vectors and checks them later. This repository is the public HTTP contract for its accountless Agent API at `https://api.trymnemo.com`.**

## What this repository is

The public contract for the **accountless Mnemo Agent API**. An agent with no account and no person in the loop:

1. **Namespace** — `POST /v1/agent/namespaces` creates a short-lived namespace (default 24 h, at most 72 h) and returns a capability once; send it as `X-Mnemo-Capability`.
2. **Embed** — `POST /v1/embed` returns a measurably perturbed watermarked copy of your vector and a `vector_uid`. Free.
3. **Lineage** — `GET /v1/lineage/{vector_uid}` returns the verified derivation chain recorded with `parent` at embed time. Free.
4. **Verify (paid)** — `POST /v1/verify` answers `402` with `PAYMENT-REQUIRED`; pay via x402 on Base and resend the identical body with `PAYMENT-SIGNATURE`. Each completed verification, positive or negative, costs 0.01 USDC (see §1 of [`agent-protocol.md`](agent-protocol.md)).

**Scope of verify.** Mnemo Verify checks whether a submitted vector resolves to an object registered to the caller's Mnemo account or namespace. `verified: false` is a normal, charged result; it is not a statement about who else may have registered the vector.

`agent-protocol.md` is the reference when anything here differs.

## Have an account API key? Use the Python SDK instead

Account holders call the same API with `X-API-Key` under their subscription plan (never x402). Use the official Python SDK:

```bash
pip install mnemo-protocol
```

```python
from mnemo_sdk import MnemoClient

client = MnemoClient(api_key="your-api-key")
```

- SDK repository: https://github.com/MnemoProtocol/mnemo-sdk
- PyPI: https://pypi.org/project/mnemo-protocol/ (distribution `mnemo-protocol`, import `mnemo_sdk`; the unrelated PyPI projects `mnemo`, `mnemo-sdk`, `mnemo-ai` and `mnemo-mcp` are not Mnemo's)
- SDK docs: https://www.trymnemo.com/docs/sdk?src=github

The SDK does not implement accountless namespaces, lineage or x402; for those, use this contract over HTTP.

## Contract files

| File | In this repo | On trymnemo.com | Contents |
|---|---|---|---|
| `agent-protocol.md` | [agent-protocol.md](agent-protocol.md) | https://www.trymnemo.com/agent-protocol.md | the complete contract: auth, lifecycle, pricing, x402, retries, lineage, promotion, retention, limits, errors |
| `openapi.json` | [openapi.json](openapi.json) | https://www.trymnemo.com/openapi.json | OpenAPI 3.1 for the six agent operations |
| `llms.txt` | [llms.txt](llms.txt) | https://www.trymnemo.com/llms.txt | discovery summary for agents |
| `agent-manifest.json` | [agent-manifest.json](agent-manifest.json) | https://www.trymnemo.com/agent-manifest.json | machine-readable manifest |
| `examples/agent-quickstart.sh` | [examples/agent-quickstart.sh](examples/agent-quickstart.sh) | https://www.trymnemo.com/examples/agent-quickstart.sh | end-to-end walkthrough with curl (placeholders only) |
| `examples/agent_quickstart.py` | [examples/agent_quickstart.py](examples/agent_quickstart.py) | https://www.trymnemo.com/examples/agent_quickstart.py | the same in Python, including the paid verify (placeholders only) |

## When not to use Mnemo

- To establish truth, authorship, ownership or authenticity of content: Mnemo does not determine any of these.
- To check whether a vector belongs to someone else: verify only resolves objects registered to your own account or namespace.
- For raw text, images, audio or video: Mnemo works on embedding vectors (512–4096 numbers).
- When your pipeline must keep the original vector bit-for-bit: embed returns a perturbed copy that you store in its place.
- Through MCP: there is no public MCP server; use the HTTP API.
- On the accountless (x402) path, for personal data subject to EEA, UK or Swiss data protection law (see the DPA note in [`llms.txt`](llms.txt)).

## Legal

Access to or use of the Mnemo API through an automated agent, application, script, SDK, protocol client, wallet, autonomous system, or other automated means constitutes access to and use of the Services by the person or entity that operates, controls, authorizes, deploys, or causes that system to access the Services, and acceptance of the Mnemo Terms of Service (Terms 1.2 and 1.5). [Terms of Service](https://www.trymnemo.com/terms) · [Privacy Policy](https://www.trymnemo.com/privacy) · [Pricing](https://www.trymnemo.com/pricing) · Security reports: security@trymnemo.com (see [SECURITY.md](SECURITY.md)).

Copyright © Mnemo LLC. All rights reserved. Patent pending. Viewing this repository does not grant a license; rights are granted only as expressly stated in the applicable license and Terms of Service.
