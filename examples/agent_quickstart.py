"""Mnemo Agent API — Python walkthrough.

Protocol: https://www.trymnemo.com/agent-protocol.md

    pip install "x402[evm]==2.22.0"   # only for paying; steps 1-4 need nothing but Python 3.9+
    export WALLET_PRIVATE_KEY=0x...   # a wallet holding USDC on Base (placeholder — never commit a key)
    python agent_quickstart.py

Every credential in this file is a placeholder. Mnemo never sees your wallet key: the x402
client signs locally and sends only the signed authorization.
"""
from __future__ import annotations

import json
import math
import os
import http.client
import random
import time
import urllib.error
import urllib.request
import uuid

API = os.environ.get("API_BASE", "https://api.trymnemo.com")


def call(method, path, body=None, headers=None):
    """One HTTP call. Returns (status, headers, json_body)."""
    req = urllib.request.Request(
        API + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"null")


def new_request_id():
    """request_id is not scoped to your namespace and is kept for 24 hours: always a fresh UUID.
    (A paid verify sends none: the payment identifies it.)"""
    return str(uuid.uuid4())


def random_vector(dim=768):
    v = [random.gauss(0, 1) for _ in range(dim)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def sign_payment(payment_required_header: str) -> str:
    """Turn the 402's PAYMENT-REQUIRED header into a PAYMENT-SIGNATURE header (x402 V2,
    exact scheme, EIP-3009 on Base). Every value — amount, payTo, the USDC signing domain —
    comes from the 402 itself."""
    from eth_account import Account
    from x402 import PaymentPayload
    from x402.http.utils import decode_payment_required_header, encode_payment_signature_header
    from x402.mechanisms.evm.exact import ExactEvmClientScheme
    from x402.mechanisms.evm.signers import EthAccountSigner

    required = decode_payment_required_header(payment_required_header)
    requirements = required.accepts[0]          # exact / eip155:8453 / USDC / 10000
    signer = EthAccountSigner(Account.from_key(os.environ["WALLET_PRIVATE_KEY"]))
    payload = ExactEvmClientScheme(signer).create_payment_payload(requirements)
    return encode_payment_signature_header(PaymentPayload(
        x402_version=2, accepted=requirements, payload=payload, resource=required.resource))


def paid_verify(cap: str, vector: list):
    """Verify, paying once if Mnemo asks. Never pays twice for the same verification.

    One body per verification and no request_id: the payment identifies the operation, so every
    retry below resends the identical body with the same PAYMENT-SIGNATURE."""
    body = {"vector": vector}
    headers = {"X-Mnemo-Capability": cap}
    status, h, out = call("POST", "/v1/verify", body, headers)
    if status != 402:
        return status, out                                  # already funded, or an error
    if "PAYMENT-REQUIRED" not in {k.upper() for k in h}:
        raise RuntimeError(f"402 without payment requirements: {out}")  # e.g. < 120 s of lifetime left
    payment = sign_payment(next(v for k, v in h.items() if k.upper() == "PAYMENT-REQUIRED"))
    headers["PAYMENT-SIGNATURE"] = payment
    for _ in range(4):
        try:
            status, h, out = call("POST", "/v1/verify", body, headers)
        except (OSError, http.client.HTTPException, ValueError):
            # No (readable) response: the outcome is unknown. Resend the identical request; if it
            # already ran you get its stored result, never a second charge.
            status, h, out = None, {}, {"code": "no_response"}
            continue

        code = out.get("code") if isinstance(out, dict) else None
        if status == 503 and code == "verification_unavailable":
            continue          # nothing was charged; the same payment funds the retry
        if status == 409 and code == "request_in_progress":
            time.sleep(2)     # an earlier attempt with this payment is still running
            continue
        if status == 402 and code == "insufficient_credits":
            time.sleep(5)     # not funded yet (refused, or settlement not final): same payment again
            continue
        return status, out
    # Out of attempts. "no_response": outcome unknown -- resend later with the SAME payment, do not
    # pay again. A bare 402: still unfunded. Keep resending the SAME payment with backoff until 90
    # minutes after its validBefore, then stop (protocol §5). Never sign a new payment automatically:
    # it would be a second payment. If the first settles late, it becomes a credit in this namespace.
    return status, out


def main():
    # 1. Create a namespace (no account). The capability is shown once.
    status, _, ns = call("POST", "/v1/agent/namespaces", {"ttl_seconds": 86400, "agent_id": "quickstart"})  # body required; {} is enough
    assert status == 201, (status, ns)        # 404 means accountless access is not enabled
    cap = ns["capability"]
    print("namespace", ns["tenant_id"], "expires", ns["expires_at"])

    # 2. Embed. Keep the WATERMARKED vector and the vector_uid.
    status, _, obj = call("POST", "/v1/embed", {"vector": random_vector(), "model_id": "quickstart-model",
                                                 "request_id": new_request_id()}, {"X-Mnemo-Capability": cap})
    assert status == 200, (status, obj)
    uid, watermarked = obj["vector_uid"], obj["watermarked_vector"]

    # 2b. A derived object with a verified parent (lineage).
    status, _, child = call("POST", "/v1/embed", {
        "vector": random_vector(), "model_id": "quickstart-model", "request_id": new_request_id(),
        "parent": {"vector_uid": uid, "relation": "summary", "vector": watermarked}},
        {"X-Mnemo-Capability": cap})
    assert status == 200, (status, child)

    # 3. Namespace status: state, expiry, usage, limits.
    print(call("GET", "/v1/agent/namespace", headers={"X-Mnemo-Capability": cap})[2])

    # 4. Lineage of the child: one ancestor (the parent), relation "summary". Free.
    print(call("GET", f"/v1/lineage/{child['vector_uid']}", headers={"X-Mnemo-Capability": cap})[2])

    # 5-8. Verify: 402 -> pay -> 200 (positive or negative, one verification either way);
    #      a 503 is retried with the same payment and is never charged.
    status, result = paid_verify(cap, watermarked)
    print(status, result)          # {"verified": true, "vector_uid": "<uid>", ...}
    status, result = paid_verify(cap, random_vector())
    print(status, result)          # {"verified": false, "vector_uid": null, ...} — still charged

    # 9. Optional, human-assisted -- an autonomous agent can stop here. To keep the data, a person
    #    signed in at https://www.trymnemo.com/login promotes the namespace:
    #    POST /v1/agent/namespace/promote with X-Mnemo-Capability (this namespace's capability) and
    #    Authorization: Bearer <that person's session token>, at least 5 minutes before
    #    expires_at. The response's one-time "credential" is the account's X-API-Key.
    print("done; the namespace expires at", ns["expires_at"], "unless a person promotes it")


if __name__ == "__main__":
    main()
