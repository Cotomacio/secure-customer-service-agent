"""
Local sanity check for the lookup_order tool — runs against the real bucket
using YOUR application default credentials, NOT Ada's identity.

This catches CSV/parsing bugs before you spend 10 minutes on a deploy.
"""

from agent.tools import lookup_order


def main() -> None:
    for oid in ["ACME-78214", "ACME-78216", "DOES-NOT-EXIST"]:
        print(f"\n>> {oid}")
        print(lookup_order(oid))


if __name__ == "__main__":
    main()
