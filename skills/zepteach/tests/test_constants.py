"""The provenance rule: a number with no stated source may not exist.

This file is the enforcement. It does not check that the values are right -
nothing can - it checks that every one of them is honest about what kind of
claim it is making, and that the code actually uses the registry rather than
quietly keeping its own copy.
"""

import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import constants as K  # noqa: E402
import review as rv  # noqa: E402
import session as se  # noqa: E402
import learner as ln  # noqa: E402


class TestEveryNumberDeclaresItself:
    def test_the_registry_is_not_empty(self):
        assert len(K.TUNABLE) > 20

    def test_each_entry_declares_a_recognised_kind(self):
        for name, spec in K.TUNABLE.items():
            assert spec.get("kind") in K.KINDS, name

    def test_each_entry_names_a_source(self):
        for name, spec in K.TUNABLE.items():
            assert spec.get("source", "").strip(), name

    def test_each_entry_explains_itself(self):
        for name, spec in K.TUNABLE.items():
            assert len(spec.get("why", "")) > 40, name

    def test_an_evidence_claim_cites_something_checkable(self):
        # a year and an author, at minimum; "research shows" is not a source
        for name, spec in K.TUNABLE.items():
            if spec["kind"] != "evidence":
                continue
            assert re.search(r"(19|20)\d{2}", spec["source"]), name
            assert not re.match(r"^(research|studies|it is known)",
                                spec["source"].lower()), name

    def test_a_number_with_no_source_says_so_plainly(self):
        # engineering entries are allowed to have no external source, but
        # they must admit it rather than dress it up
        for name, spec in K.TUNABLE.items():
            if spec["kind"] != "engineering":
                continue
            src = spec["source"].lower()
            assert ("none" in src or "no " in src or "not a study" in src
                    or "after" in src or "variant" in src
                    or "scaled from" in src or "tighter than" in src), name

    def test_placeholders_are_marked_for_calibration(self):
        # anything whose honest answer is "it depends on the person" has to
        # be learned from that person, not shipped as a fact
        calibrated = {n for n, s in K.TUNABLE.items()
                      if s["kind"] == "calibrated"}
        assert "session_minutes" in calibrated
        assert "energy_scaling" in calibrated

    def test_the_debunked_attention_figure_is_not_used_as_a_basis(self):
        src = K.TUNABLE["session_minutes"]["source"].lower()
        assert "wilson" in src and "korn" in src
        assert "not the 10-15" in src

    def test_the_weakest_number_admits_it(self):
        assert "weakest" in K.TUNABLE["grade_factor"]["why"]


class TestTheCodeUsesTheRegistry:
    def test_review_reads_its_numbers_from_constants(self):
        assert rv.DEFAULT_EASE is K.DEFAULT_EASE
        assert rv.MAX_INTERVAL_DAYS is K.MAX_INTERVAL_DAYS
        assert rv.GRADE_TABLE is K.GRADE_TABLE

    def test_session_reads_its_numbers_from_constants(self):
        assert se.ENERGY is K.ENERGY
        assert se.TURN_BUDGET is K.TURN_BUDGET

    def test_learner_reads_its_numbers_from_constants(self):
        assert ln.BYPASS_WARNING_COUNT is K.BYPASS_WARNING_COUNT

    def test_the_floors_come_from_the_registry(self):
        assert rv.floor_days("delayed_retest", {}) == \
            K.DELAYED_RETEST_MIN_DAYS
        assert rv.floor_days("transfer_test", {}) == K.TRANSFER_TEST_MIN_DAYS

    def test_no_bare_magic_numbers_are_left_in_the_scheduler(self):
        """A crude but effective guard: the scheduling maths must not contain
        freshly invented decimals that bypassed the registry."""
        src = (SCRIPTS / "review.py").read_text(encoding="utf-8")
        body = src.split("def grade_of")[1]
        suspicious = set(re.findall(r"(?<![\w.])0\.\d+", body))
        # 0.0 and 0.1/0.08/0.02 are the published SM-2 ease formula
        allowed = {"0.0", "0.1", "0.08", "0.02", "0.9"}
        assert suspicious <= allowed, sorted(suspicious - allowed)


class TestTheLedgerIsReadable:
    def test_the_table_prints(self, capsys):
        assert K.main(["table"]) == 0
        out = capsys.readouterr().out
        assert "EVIDENCE" in out and "ENGINEERING" in out
        assert "CALIBRATED" in out

    def test_the_table_counts_every_entry(self, capsys):
        K.main(["table"])
        out = capsys.readouterr().out
        total = sum(int(part.split(": ")[1])
                    for part in out.strip().splitlines()[-1].split(", "))
        assert total == len(K.TUNABLE)

    def test_you_can_list_just_the_guesses(self, capsys):
        assert K.main(["kind", "engineering"]) == 0
        names = capsys.readouterr().out.split()
        assert "turn_budget" in names
        assert "delayed_retest_min_days" not in names
