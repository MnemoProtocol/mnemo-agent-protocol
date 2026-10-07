# Mnemo Agent API — public protocol

Verifiable identity for embedding vectors. Agents create a short-lived namespace without an account, embed vectors,
read verified lineage, and pay per verification with USDC via x402 on Base. Calls made with an account API key use
the account's subscription plan instead (see Pricing in `agent-protocol.md`).

This repository holds the machine-facing contract for `https://api.trymnemo.com`.

| File | Contents |
|---|---|
| [`agent-protocol.md`](agent-protocol.md) | the complete contract: auth, lifecycle, pricing, x402, retries, lineage, promotion, retention, limits, errors |
| [`openapi.json`](openapi.json) | OpenAPI 3.1 for the six agent operations |
| [`llms.txt`](llms.txt) | discovery summary for agents |
| [`agent-manifest.json`](agent-manifest.json) | machine-readable manifest |
| [`examples/agent-quickstart.sh`](examples/agent-quickstart.sh) | end-to-end walkthrough with curl (placeholders only) |
| [`examples/agent_quickstart.py`](examples/agent_quickstart.py) | the same in Python, including the paid verify (placeholders only) |

`agent-protocol.md` is the reference when anything here differs.
