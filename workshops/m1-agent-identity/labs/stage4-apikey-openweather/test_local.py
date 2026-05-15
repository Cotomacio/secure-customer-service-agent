"""Local sanity check — runs lookup_order via your ADC."""
from agent.tools import lookup_order


def main() -> None:
    for oid in ["ACME-78214", "ACME-78216", "DOES-NOT-EXIST"]:
        print(f"\n>> {oid}")
        print(lookup_order(oid))


if __name__ == "__main__":
    main()
