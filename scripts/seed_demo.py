"""Print a safe summary of the synthetic demo fixture."""

from quorum.data.loader import build_fixture


def main() -> None:
    organisations, sites, volunteers, shifts = build_fixture()
    print(
        f"Seeded synthetic fixture: organisations={len(organisations)} sites={len(sites)} "
        f"volunteers={len(volunteers)} shifts={len(shifts)}"
    )


if __name__ == "__main__":
    main()
