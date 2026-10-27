"""Deterministic payment-wording guard for the public contract files.

Accountless payments run over several rails (owner decisions 2026-10-27):
single_verify over x402 (Base) or MPP on Tempo; burst_500 also over a card
through MPP and a Stripe Shared Payment Token, never for a single
verification. This check fails on wording that made x402 the identity of
accountless billing and on a card rail offered for single_verify. It does not
police descriptions of the x402 rail itself. Standard library only.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ["README.md", "SECURITY.md", "llms.txt", "agent-protocol.md", "openapi.json",
         "agent-manifest.json", "context7.json",
         "examples/agent-quickstart.sh", "examples/agent_quickstart.py"]
# Files that describe paying for accountless verification: naming x402 there
# without MPP on Tempo reads as "x402 is the only rail".
RAIL_DOCS = ["README.md", "llms.txt", "agent-protocol.md", "openapi.json",
             "agent-manifest.json", "context7.json"]
OBSOLETE = [
    ("accountless (x402)", re.compile(r"accountless \(x402\)", re.I)),
    ("x402 entitlement", re.compile(r"x402[ _-]entitlement", re.I)),
    ("x402 accountless", re.compile(r"x402 accountless", re.I)),
    ("pay-per-verify (x402)", re.compile(r"pay-per-verify \(x402\)", re.I)),
    ("usable_until (the public field is retained_until)", re.compile(r"usable_until")),
]

errors = []
text = {f: (ROOT / f).read_text(encoding="utf-8") for f in FILES}
for f, t in text.items():
    for label, rx in OBSOLETE:
        if rx.search(t):
            errors.append(f"{f}: obsolete wording '{label}'")
for f in RAIL_DOCS:
    if "x402" in text[f] and "Tempo" not in text[f]:
        errors.append(f"{f}: names x402 without MPP on Tempo")

manifest = json.loads(text["agent-manifest.json"])
offers = {o["id"]: sorted(o["rails"]) for o in manifest["offers"]}
if offers.get("single_verify") != ["mpp_tempo", "x402"]:
    errors.append(f"agent-manifest.json: single_verify rails {offers.get('single_verify')} != ['mpp_tempo', 'x402']")
if offers.get("burst_500") != ["mpp_tempo", "stripe_spt", "x402"]:
    errors.append(f"agent-manifest.json: burst_500 rails {offers.get('burst_500')} != ['mpp_tempo', 'stripe_spt', 'x402']")

openapi = json.loads(text["openapi.json"])
for path, want in (("/v1/verify", ["mpp_tempo", "x402"]),
                   ("/v1/agent/namespace/fund", ["mpp_tempo", "stripe_spt", "x402"])):
    got = sorted(r["id"] for r in openapi["paths"][path]["post"]["x-payment-rails"])
    if got != want:
        errors.append(f"openapi.json: {path} x-payment-rails {got} != {want}")

for e in errors:
    print(f"::error::{e}")
print(f"payment wording: {len(errors)} problem(s) in {len(FILES)} files")
sys.exit(1 if errors else 0)
