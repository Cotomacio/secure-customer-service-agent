"""
Local sanity check — runs lookup_order against the real bucket using YOUR ADC.

Stage 2's ServiceNow tool (lookup_incidents) can't be tested locally because
it depends on Agent Identity Auth Manager injecting a credential at runtime.
Test that via deployed `python chat.py` instead.
"""

from agent.tools import lookup_order


def main() -> None:
    for oid in ["ACME-78214", "ACME-78216", "DOES-NOT-EXIST"]:
        print(f"\n>> {oid}")
        print(lookup_order(oid))


if __name__ == "__main__":
    main()
