"""E464: post-cleanup material evidence cannot leak into reopened hotspots.

Synthetic declarations only. Provenance is not independently authenticated.
"""
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
OLD = NOW - timedelta(hours=3)
CLOSED = NOW - timedelta(hours=2)
NEW = NOW - timedelta(hours=1)


def report(name, when, *, status="open", provenance="observed",
           materials=None, source_id=None):
    return Observation(
        id=name,
        source_id=source_id or name,
        source_type="partner" if provenance == "measured" else "citizen",
        provenance=provenance,
        lat=19.076,
        lon=72.8777,
        observed_at=when,
        ingested_at=when,
        confidence=0.8,
        status=status,
        materials=materials or {},
    )


def old_plastic():
    return report("old", OLD, provenance="measured", materials={"plastic": 1.0})


def cleanup():
    return report("clean", CLOSED, status="cleaned", provenance="verified_official")


def test_reopened_materials_exclude_old_high_provenance_plastic():
    h = fuse_cluster(
        [old_plastic(), cleanup(), report("new", NEW, materials={"glass": 1.0})], NOW
    )
    assert h.status == "open"
    assert h.materials == {"glass": 1.0}


def test_reopened_without_material_evidence_abstains():
    h = fuse_cluster([old_plastic(), cleanup(), report("new", NEW)], NOW)
    assert h.materials == {}


def test_equal_time_reopening_does_not_attribute_boundary_materials():
    h = fuse_cluster(
        [old_plastic(), cleanup(), report("new", CLOSED, materials={"glass": 1.0})],
        NOW,
    )
    assert h.status == "open"
    assert h.materials == {}


def test_closed_hotspot_preserves_historical_materials():
    h = fuse_cluster([old_plastic(), cleanup()], NOW)
    assert h.status == "cleaned"
    assert h.materials == {"plastic": 1.0}


def test_unverified_citizen_cleanup_does_not_reset_material_episode():
    unverified = report("unverified", CLOSED, status="cleaned")
    h = fuse_cluster(
        [old_plastic(), unverified, report("new", NEW, materials={"glass": 1.0})],
        NOW,
    )
    assert h.materials == {"plastic": 1.0, "glass": 1.0}


def test_new_report_same_source_not_suppressed_by_older_stronger_report():
    h = fuse_cluster(
        [
            old_plastic(),
            cleanup(),
            report("new", NEW, source_id="old", materials={"glass": 1.0}),
        ],
        NOW,
    )
    assert h.materials == {"glass": 1.0}


def test_latest_credible_cleanup_defines_material_epoch():
    second = report(
        "second", NOW - timedelta(minutes=45),
        status="verified", provenance="measured",
    )
    h = fuse_cluster(
        [
            old_plastic(),
            cleanup(),
            report("interim", NEW, materials={"glass": 1.0}),
            second,
            report("latest", NOW - timedelta(minutes=15), materials={"paper": 0.75}),
        ],
        NOW,
    )
    assert h.materials == {"paper": 0.75}
