"""Create a believable, wholly synthetic Riverside Food Bank world."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quorum.domain.models import Organisation, Role, Shift, Site, Volunteer
from quorum.persistence.memory import MemoryStore


def build_fixture(now: datetime | None = None) -> tuple[list[Organisation], list[Site], list[Volunteer], list[Shift]]:
    now = now or datetime.now(timezone.utc)
    organisation = Organisation(id="org:riverside", name="Riverside Food Bank")
    sites = [
        Site(id=f"site-{index}", organisation_id=organisation.id, name=name, travel_zone=index)
        for index, name in enumerate(
            ["River Hall", "North Pantry", "East Depot", "Meadow Hub", "South Kitchen", "West Store"], start=1
        )
    ]
    shifts = [
        Shift(
            id=f"shift-{index}",
            organisation_id=organisation.id,
            site_id=sites[(index - 1) % len(sites)].id,
            starts_at=now + timedelta(hours=4 + index * 3),
            ends_at=now + timedelta(hours=7 + index * 3),
            required_by_role={Role.DRIVER: 1, Role.SORTER: 2},
        )
        for index in range(1, 7)
    ]
    all_shift_ids = {shift.id for shift in shifts}
    archetypes = [
        ("reliable", 12, 1, 9, 1, False, 34, True),
        ("late-canceller", 3, 7, 4, 5, False, 42, True),
        ("slow-responder", 6, 2, 3, 2, False, 29, True),
        ("needs-transport", 8, 2, 6, 2, True, 38, True),
        ("partial-availability", 7, 2, 5, 2, False, 31, True),
        ("frequent-decliner", 8, 2, 2, 9, False, 45, True),
        ("newcomer", 0, 0, 0, 0, False, 26, True),
        ("ambiguous-responder", 5, 2, 4, 3, False, 33, True),
        ("injured-out-of-scope", 9, 1, 8, 1, False, 40, True),
        ("complaint-case", 4, 3, 3, 3, False, 36, True),
        ("prompt-injection-case", 6, 1, 5, 2, False, 30, True),
        ("minor-driver-blocked", 8, 1, 7, 1, False, 16, True),
    ]
    volunteers: list[Volunteer] = []
    for index in range(36):
        archetype, rs, rf, accepted, declined, needs_transport, age, checked = archetypes[index % len(archetypes)]
        roles = {Role.SORTER} if index % 3 == 0 else {Role.DRIVER, Role.SORTER}
        available = all_shift_ids if archetype != "partial-availability" else {"shift-1", "shift-3"}
        volunteers.append(
            Volunteer(
                id=f"vol-{index + 1:02d}",
                display_name=f"Synthetic Volunteer {index + 1:02d}",
                roles=roles,
                age=age,
                background_check=checked,
                available_shift_ids=available,
                travel_zones={1, 2, 3} if index % 2 == 0 else {2, 3, 4, 5, 6},
                reliability_successes=rs,
                reliability_failures=rf,
                accepted=accepted,
                declined=declined,
                needs_transport=needs_transport,
                archetype=archetype,
            )
        )
    return [organisation], sites, volunteers, shifts


def seed_store(store: MemoryStore, now: datetime | None = None) -> MemoryStore:
    store.seed(*build_fixture(now))
    return store
