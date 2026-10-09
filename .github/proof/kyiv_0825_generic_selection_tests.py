#!/usr/bin/env python3
"""Generic synthetic tests for UNIQUE_LATE_CLOCK_AND_FREE_SLOT only."""
import importlib.util
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
scripts=root/"kyiv-air-alerts-grafana/scripts"
sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location("actual_repaired_monitor_generic_test",scripts/"monitor_explosion_candidates.py")
mon=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mon)
mon.classification_segments=lambda row:list(row["segments"])
mon.city_mentioned=lambda city,segment:not segment.startswith("skip")
mon.strict_attack_event_signal=lambda segment:segment.startswith("!")
mon.event_clock_mentions=lambda segment: [(8,25)] if "@1" in segment else ([(8,25),(9,10)] if "@2" in segment else [])
def case(name,segments,expected):
    got=mon.exact_city_classification_evidence("any_city",{"segments":segments})
    assert got["segments"]==expected,(name,got,expected)
    assert got["present"]==bool([s for s in segments if not s.startswith("skip")]),name
    assert len(got["segments"])<=4,name
    print("GENERIC_TEST_PASS="+name,flush=True)
case("unique_late_one_clock_and_free_slot",["!a","?b","?c","!d","!@1e"],["!a","?b","!d","!@1e"])
case("no_qualifying_late",["!a","?b","?c","!d","?e"],["!a","?b","?c","!d"])
case("two_qualifying_late",["!a","?b","?c","!d","!@1e","!@1f"],["!a","?b","?c","!d"])
case("late_strict_no_clock",["!a","?b","?c","!d","!e"],["!a","?b","?c","!d"])
case("late_strict_two_clocks",["!a","?b","?c","!d","!@2e"],["!a","?b","?c","!d"])
case("retained_strict_already_clocked",["!@1a","?b","?c","!d","!@1e"],["!@1a","?b","?c","!d"])
case("all_four_retained_strict",["!a","!b","!c","!d","!@1e"],["!a","!b","!c","!d"])
case("exactly_four_city_segments",["!a","?b","?c","!d"],["!a","?b","?c","!d"])
case("source_order_and_last_nonstrict_replacement",["?a","!b","?c","!d","!@1e"],["?a","!b","!d","!@1e"])
case("cap_never_above_four",["?a","!b","?c","!d","?e","!@1f","?g"],["?a","!b","!d","!@1f"])
case("city_filter_before_cap",["skip0","!a","?b","?c","!d","!@1e"],["!a","?b","!d","!@1e"])
case("no_city_segments",["skip0","skip1"],[])
print("GENERIC_SELECTION_TESTS=12/12_PASS",flush=True)
