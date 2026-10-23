"""Phase 5: location slugs, region cleanup, markdown export, UTC timestamps, enrichment CLI."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from relocation.database import enable_sqlite_foreign_keys
from relocation.export_markdown import export_locations, stale_files
from relocation.migrate import upgrade_database
from relocation.models import Location, ResearchRun
from relocation.slugs import location_slug, slugify


def test_slugify_folds_accents_and_punctuation():
    assert slugify("Rincón") == "rincon"
    assert slugify("Alcalá") == "alcala"
    assert slugify("Todos Santos / Cerritos") == "todos-santos-cerritos"
    assert slugify("Itacaré") == "itacare"
    assert slugify("Øresund Straße") == "oresund-strasse"
    assert location_slug("Esperanza, Vieques", "Puerto Rico") == "esperanza-vieques-puerto-rico"


def test_new_location_gets_slug_from_jurisdiction_name(db_session):
    loc = Location(name="Rincón", country="Puerto Rico", country_code="PR")
    db_session.add(loc)
    db_session.commit()
    assert loc.slug == "rincon-puerto-rico"


def test_slug_collisions_and_renames(db_session):
    first = Location(name="San José", country="Costa Rica", country_code="CR", region="Central")
    second = Location(name="San Jose", country="Costa Rica ", country_code="CR", region="Guanacaste")
    db_session.add_all([first, second])
    db_session.commit()
    assert first.slug == "san-jose-costa-rica"
    assert second.slug == "san-jose-costa-rica-guanacaste"

    first.name = "San José Centro"
    db_session.commit()
    assert first.slug == "san-jose-centro-costa-rica"

    first.notes = "unrelated edit"
    db_session.commit()
    assert first.slug == "san-jose-centro-costa-rica"


def test_migration_backfills_slugs_and_fixes_regions(tmp_path):
    engine = enable_sqlite_foreign_keys(create_engine(f"sqlite:///{tmp_path / 'm.db'}"))
    upgrade_database(engine, "0006_research_key_facts")
    with engine.begin() as conn:
        conn.execute(text("INSERT OR IGNORE INTO countries (code, name, created_at) VALUES ('US', 'United States', '2026-01-01')"))
        conn.execute(text(
            "INSERT OR IGNORE INTO countries (code, name, parent_code, created_at) VALUES ('PR', 'Puerto Rico', 'US', '2026-01-01')"
        ))
        conn.execute(text("INSERT OR IGNORE INTO countries (code, name, created_at) VALUES ('PT', 'Portugal', '2026-01-01')"))
        for name, country, code, region in [
            ("Rincón", "Puerto Rico", "PR", "Puerto Rico"),
            ("Funchal", "Portugal", "PT", "Madiera"),
            ("Brooklyn", "United States", "US", " New York "),
            ("Brooklyn", "USA", "US", "New York"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO locations (name, country, country_code, region, created_at, updated_at) "
                    "VALUES (:n, :c, :code, :r, '2026-01-01', '2026-01-01')"
                ),
                {"n": name, "c": country, "code": code, "r": region},
            )
    upgrade_database(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, slug, region FROM locations ORDER BY id")).fetchall()
    engine.dispose()
    assert [tuple(r) for r in rows] == [
        ("Rincón", "rincon-puerto-rico", "Puerto Rico"),
        ("Funchal", "funchal-portugal", "Madeira"),
        ("Brooklyn", "brooklyn-united-states", "New York"),
        ("Brooklyn", "brooklyn-united-states-new-york", "New York"),
    ]


def test_export_writes_slug_file_and_finds_stale(db_session, tmp_path):
    loc = Location(name="Rincón", country="Puerto Rico", country_code="PR")
    db_session.add(loc)
    db_session.commit()
    (tmp_path / "rinc-n-usa.md").write_text("old")
    (paths,) = [export_locations(db_session, [loc], tmp_path)]
    assert paths == [tmp_path / "rincon-puerto-rico.md"]
    assert paths[0].read_text().startswith("# Rincón (Puerto Rico)")
    assert [p.name for p in stale_files(db_session, tmp_path)] == ["rinc-n-usa.md"]


def test_timestamps_read_back_as_aware_utc(db_session):
    loc = Location(name="Testville", country="Peru", country_code="PE")
    db_session.add(loc)
    local = datetime(2026, 10, 23, 9, 0, tzinfo=timezone(timedelta(hours=-4)))
    run = ResearchRun(kind="full", status="completed", started_at=local)
    db_session.add(run)
    db_session.commit()
    db_session.expire_all()
    assert loc.created_at.tzinfo is not None
    stored = db_session.execute(text("SELECT started_at FROM research_runs WHERE id = :id"), {"id": run.id}).scalar()
    assert str(stored).startswith("2026-10-23 13:00:00")
    assert db_session.get(ResearchRun, run.id).started_at == datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)


def test_api_serialises_timestamps_with_offset(client, db_session):
    db_session.add(Location(name="Testville", country="Peru", country_code="PE"))
    db_session.commit()
    body = client.get("/api/v1/locations", params={"current_research_only": False}).json()
    created = next(item for item in body if item["name"] == "Testville")["created_at"]
    assert created.endswith("Z") or created.endswith("+00:00")


def test_research_markdown_endpoint_builds_from_db(client, db_session):
    loc = Location(name="Rincón", country="Puerto Rico", country_code="PR")
    other = Location(name="Rincón Viejo", country="Puerto Rico", country_code="PR")
    db_session.add_all([loc, other])
    db_session.commit()
    response = client.get(f"/api/v1/locations/{loc.id}/research-markdown")
    assert response.status_code == 200
    assert response.text.startswith("# Rincón (Puerto Rico)")
    assert client.get("/api/v1/locations/999999/research-markdown").status_code == 404
