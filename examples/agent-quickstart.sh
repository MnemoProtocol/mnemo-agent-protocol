#!/usr/bin/env bash
# Mnemo Agent API — curl walkthrough (protocol: https://www.trymnemo.com/agent-protocol.md).
#
# Needs: bash, curl, python3. Paying (step 6) needs an x402 V2 client and a wallet holding
# USDC on Base; see agent_quickstart.py for a complete signing example.
#
# Every credential below is a placeholder. Never paste a real capability, API key, session
# token or payment signature into a file you share.
set -euo pipefail

API="${API_BASE:-https://api.trymnemo.com}"
JSON='Content-Type: application/json'

# A random 768-dimension unit vector stands in for your embedding.
vector() { python3 -c 'import json,math,random; v=[random.gauss(0,1) for _ in range(768)]; n=math.sqrt(sum(x*x for x in v)); print(json.dumps([x/n for x in v]))'; }
field() { python3 -c "import json,sys; v=json.load(sys.stdin)$1; print(v if isinstance(v, str) else json.dumps(v))"; }
# request_id is not scoped to your namespace and is kept for 24 hours: always use a fresh UUID.
rid() { python3 -c 'import uuid; print(uuid.uuid4())'; }

# 1. Create an ephemeral namespace. No account. Send a JSON body ({} is enough).
#    The capability is shown ONCE — store it.
CREATED=$(curl -sS -X POST "$API/v1/agent/namespaces" -H "$JSON" -d '{"ttl_seconds": 86400, "agent_id": "quickstart"}')
CAP=$(echo "$CREATED" | field "['capability']")          # mnemo_eph_...
echo "namespace expires at: $(echo "$CREATED" | field "['expires_at']")"

# 2. Embed. Store the watermarked vector (it carries the identity) and the vector_uid.
EMBEDDED=$(curl -sS -X POST "$API/v1/embed" -H "X-Mnemo-Capability: $CAP" -H "$JSON" \
  -d "{\"vector\": $(vector), \"model_id\": \"quickstart-model\", \"request_id\": \"$(rid)\"}")
UID_=$(echo "$EMBEDDED" | field "['vector_uid']")
WATERMARKED=$(echo "$EMBEDDED" | field "['watermarked_vector']")

# 3. Inspect the namespace: state, expiry, usage, limits.
curl -sS "$API/v1/agent/namespace" -H "X-Mnemo-Capability: $CAP"; echo

# 4. Lineage of the object (a root here: depth 0, no ancestors). Free.
curl -sS "$API/v1/lineage/$UID_" -H "X-Mnemo-Capability: $CAP"; echo

# 5. Verify without paying → 402 with a PAYMENT-REQUIRED header (base64 JSON, x402 V2).
#    No request_id on a paid verify: the payment identifies it, so every retry resends this exact BODY.
BODY="{\"vector\": $WATERMARKED}"
curl -sS -D /tmp/mnemo_402_headers -o /dev/null -X POST "$API/v1/verify" \
  -H "X-Mnemo-Capability: $CAP" -H "$JSON" -d "$BODY"
PAYMENT_REQUIRED=$(grep -i '^payment-required:' /tmp/mnemo_402_headers | cut -d' ' -f2- | tr -d '\r')
echo "$PAYMENT_REQUIRED" | base64 --decode | python3 -m json.tool   # scheme, network, asset, amount, payTo, extra

# 6. Pay with an x402 V2 client using the requirements above, then send the SAME BODY again with
#    the payment. Placeholder — produce your own:
PAYMENT_SIGNATURE="${PAYMENT_SIGNATURE:-EXAMPLE_BASE64_PAYMENT_PAYLOAD_DO_NOT_USE}"
curl -sS -D /tmp/mnemo_200_headers -X POST "$API/v1/verify" \
  -H "X-Mnemo-Capability: $CAP" -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE" -H "$JSON" -d "$BODY"; echo

# 7. The 200 is a healthy result: "verified": true (with a vector_uid) or "verified": false
#    (vector_uid null). Both cost one verification. PAYMENT-RESPONSE (on a 200 where the payment
#    settled) carries the settlement. A 402 WITHOUT PAYMENT-REQUIRED here means this request was not
#    funded (refused, or settlement not final yet): resend the same BODY with the same payment, with
#    backoff, until 90 minutes after its validBefore; then stop (protocol §5). Never sign a new
#    payment automatically: it would be a second payment.
grep -i '^payment-response:' /tmp/mnemo_200_headers || true

# 8. If step 6 answered 503 {"code": "verification_unavailable"}: nothing was charged and the
#    payment stays usable. Resend the SAME BODY with the SAME PAYMENT-SIGNATURE — do not pay again:
#   curl -sS -X POST "$API/v1/verify" -H "X-Mnemo-Capability: $CAP" \
#     -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE" -H "$JSON" -d "$BODY"
#    The same applies to a timeout and to 409 {"code": "request_in_progress"} (wait a moment first).

# 9. Promote — optional and human-assisted; an autonomous agent can stop at step 8. To keep the
#    data, a person signs in at https://www.trymnemo.com/login; promotion is then this call, made
#    with the capability AND that person's session token (at least 5 minutes before expires_at):
#   curl -sS -X POST "$API/v1/agent/namespace/promote" \
#     -H "X-Mnemo-Capability: $CAP" -H "Authorization: Bearer EXAMPLE_HUMAN_SESSION_TOKEN"
#    The response's "credential" (shown once) is the account's API key: send it as X-API-Key.
