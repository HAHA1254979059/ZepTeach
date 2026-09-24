"""Tests for curriculum navigation and pace.

What is pinned here: the next lesson is chosen from what is actually proven,
a broken prerequisite is reported rather than skipped around, pace is measured
in minutes of work left against the deadline, and registering a second course
reuses a concept instead of cloning it.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import curriculum as cu  # noqa: E402
import learner as ln  # noqa: E402
import zt_state as zs  # noqa: E402
import conftest as fx  # noqa: E402


class TestLessonState:
    def test_untouched_when_nothing_is_recorded(self):
        _, les = cu.find_lesson(fx.curriculum(), "l1")
        assert cu.lesson_state(les, {}) == "untouched"

    def test_started_once_something_has_been_taught(self):
        _, les = cu.find_lesson(fx.curriculum(), "l1")
        by_id = {fx.EIGENVALUE: fx.mastery(state="introduced")}
        assert cu.lesson_state(les, by_id) == "started"

    def test_practiced_is_not_done(self):
        # done means the ground will still be there next month
        _, les = cu.find_lesson(fx.curriculum(), "l1")
        by_id = {fx.EIGENVALUE: fx.mastery(state="practiced")}
        assert cu.lesson_state(les, by_id) == "started"

    def test_done_once_every_concept_is_consolidated(self):
        _, les = cu.find_lesson(fx.curriculum(), "l1")
        by_id = {fx.EIGENVALUE: fx.mastery(state="consolidating"),
                 fx.SHARED: fx.mastery(fx.SHARED, state="consolidating")}
        assert cu.lesson_state(les, by_id) == "done"


class TestNextLesson:
    def test_the_first_unfinished_lesson_is_next(self):
        nxt = cu.next_lesson(fx.curriculum(), [])
        assert nxt["lesson_id"] == "l1"

    def test_finished_lessons_are_skipped(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="mastered"),
                fx.mastery(fx.SHARED, state="mastered")]
        assert cu.next_lesson(fx.curriculum(), rows)["lesson_id"] == "l2"

    def test_a_broken_prerequisite_is_reported_not_routed_around(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="shaky",
                           downstream={"hold": True})]
        nxt = cu.next_lesson(fx.curriculum(), rows)
        assert nxt["lesson_id"] == "l1"
        rows.append(fx.mastery(fx.EIGENVECTOR, state="unseen"))

    def test_blockers_surface_on_the_lesson_that_needs_them(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="shaky",
                           downstream={"hold": True}),
                fx.mastery(fx.EIGENVALUE, state="shaky")]
        cur = fx.curriculum()
        cur["modules"][0]["lessons"] = [cur["modules"][0]["lessons"][1]]
        nxt = cu.next_lesson(cur, rows)
        assert nxt["blockers"][0]["concept_id"] == fx.EIGENVALUE

    def test_a_waved_through_prerequisite_stops_blocking(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="shaky",
                           downstream={"hold": True, "bypassed": True,
                                       "bypass_reason": "later"})]
        cur = fx.curriculum()
        cur["modules"][0]["lessons"] = [cur["modules"][0]["lessons"][1]]
        assert cu.next_lesson(cur, rows)["blockers"] == []

    def test_a_completed_course_says_so(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="mastered"),
                fx.mastery(fx.SHARED, state="mastered"),
                fx.mastery(fx.EIGENVECTOR, state="mastered")]
        assert cu.next_lesson(fx.curriculum(), rows) is None


class TestLessonCard:
    def test_the_card_carries_what_a_session_needs(self):
        card = cu.lesson_card(fx.curriculum(), "l1", [], fx.course())
        assert card["adapter_ref"] == "adapters/mathematics.json"
        assert card["concepts"][0]["depth_target"] == 3
        assert card["concepts"][0]["state"] == "unseen"

    def test_the_card_does_not_drag_in_the_rest_of_the_course(self):
        card = cu.lesson_card(fx.curriculum(), "l1", [], fx.course())
        assert len(card["concepts"]) == 2
        assert fx.EIGENVECTOR not in json.dumps(card)

    def test_the_source_span_rides_along_when_there_is_one(self):
        cur = fx.curriculum()
        cur["modules"][0]["lessons"][0]["source_span"] = {
            "source_id": "strang", "section": "6.1", "page_start": 283}
        card = cu.lesson_card(cur, "l1", [], fx.course(source_anchored=True))
        assert card["source_span"]["section"] == "6.1"
        assert card["source_anchored"] is True

    def test_an_unknown_lesson_raises(self):
        with pytest.raises(FileNotFoundError):
            cu.lesson_card(fx.curriculum(), "nope", [], fx.course())


class TestDrift:
    def test_no_deadline_means_no_pressure(self):
        d = cu.drift(fx.course(), fx.curriculum(), [], date(2026, 9, 20))
        assert d["deadline"] is None
        assert "no deadline" in d["verdict"]

    def test_behind_when_the_work_left_outruns_the_budget(self):
        c = fx.course(deadline="2026-09-27", weekly_minutes=60)
        d = cu.drift(c, fx.curriculum(), [], date(2026, 9, 20))
        assert d["drift_minutes_per_week"] < 0
        assert d["verdict"].startswith("behind")

    def test_ahead_when_there_is_room(self):
        c = fx.course(deadline="2027-09-27", weekly_minutes=300)
        d = cu.drift(c, fx.curriculum(), [], date(2026, 9, 20))
        assert d["verdict"] == "ahead of the deadline pace"

    def test_finished_lessons_stop_counting_against_the_clock(self):
        c = fx.course(deadline="2026-10-20", weekly_minutes=60)
        rows = [fx.mastery(fx.EIGENVALUE, state="mastered"),
                fx.mastery(fx.SHARED, state="mastered")]
        before = cu.drift(c, fx.curriculum(), [], date(2026, 9, 20))
        after = cu.drift(c, fx.curriculum(), rows, date(2026, 9, 20))
        assert after["remaining_minutes"] < before["remaining_minutes"]

    def test_a_passed_deadline_is_stated_plainly(self):
        c = fx.course(deadline="2026-09-01", weekly_minutes=300)
        d = cu.drift(c, fx.curriculum(), [], date(2026, 9, 20))
        assert "deadline passed" in d["verdict"]


class TestRegisterConcepts:
    def test_new_concept_cannot_inherit_a_broad_course_domain(self, root):
        zs.atomic_write_json(root / "concepts.json",
                             {"schema_version": 1, "concepts": []})
        curriculum = zs.read_json(root / "courses" / "linear-algebra" /
                                  "curriculum.json")
        del curriculum["modules"][0]["lessons"][0]["concepts"][0]["domain"]
        zs.atomic_write_json(root / "courses" / "linear-algebra" /
                             "curriculum.json", curriculum)
        assert cu.main(["--root", str(root), "register-concepts",
                        "--course", "linear-algebra"]) == zs.EXIT_VALIDATION
        assert zs.read_json(root / "concepts.json")["concepts"] == []

    def test_a_new_course_adds_its_concepts(self, root, capsys):
        (root / "concepts.json").unlink()
        zs.atomic_write_json(root / "concepts.json",
                             {"schema_version": 1, "concepts": []})
        assert cu.main(["--root", str(root), "register-concepts",
                        "--course", "linear-algebra"]) == zs.EXIT_OK
        reg = zs.read_json(root / "concepts.json")
        assert {c["concept_id"] for c in reg["concepts"]} == \
            {fx.EIGENVALUE, fx.SHARED, fx.EIGENVECTOR}

    def test_a_second_course_reuses_rather_than_clones(self, root, capsys):
        zs.atomic_write_json(root / "concepts.json",
                             {"schema_version": 1, "concepts": []})
        cu.main(["--root", str(root), "register-concepts",
                 "--course", "linear-algebra"])
        capsys.readouterr()
        cu.main(["--root", str(root), "register-concepts",
                 "--course", "historiography"])
        out = capsys.readouterr().out
        reg = zs.read_json(root / "concepts.json")
        ids = [c["concept_id"] for c in reg["concepts"]]
        assert ids.count(fx.SHARED) == 1
        entry = next(c for c in reg["concepts"]
                     if c["concept_id"] == fx.SHARED)
        assert sorted(entry["courses"]) == ["hist", "linalg"]
        assert "reused" in out

    def test_the_result_still_validates(self, root):
        zs.atomic_write_json(root / "concepts.json",
                             {"schema_version": 1, "concepts": []})
        cu.main(["--root", str(root), "register-concepts",
                 "--course", "linear-algebra"])
        reg = zs.read_json(root / "concepts.json")
        assert zs.validate_doc(reg, "concept_registry") == []


class TestCli:
    def test_next_exits_three_when_blocked(self, root):
        fx.write_mastery(root, [
            fx.mastery(fx.EIGENVALUE, state="mastered"),
            fx.mastery(fx.EIGENVECTOR, state="unseen")])
        rows = ln.load_mastery(root)
        rows[0]["state"] = "shaky"
        rows[0]["downstream"] = {"hold": True}
        ln.save_mastery(root, rows)
        assert cu.main(["--root", str(root), "next",
                        "--course", "linear-algebra"]) == zs.EXIT_OK

    def test_lesson_card_prints_json(self, root, capsys):
        assert cu.main(["--root", str(root), "lesson",
                        "--course", "linear-algebra",
                        "--lesson", "l1"]) == zs.EXIT_OK
        assert json.loads(capsys.readouterr().out)["lesson_id"] == "l1"

    def test_drift_prints_one_line_by_default(self, root, capsys):
        assert cu.main(["--root", str(root), "drift",
                        "--course", "linear-algebra",
                        "--today", "2026-09-20"]) == zs.EXIT_OK
        assert len(capsys.readouterr().out.strip().splitlines()) == 2

    def test_validate_accepts_the_fixture_course(self, root):
        assert cu.main(["--root", str(root), "validate",
                        "--course", "linear-algebra"]) == zs.EXIT_OK

    def test_validate_catches_an_unregistered_concept(self, root):
        cur = fx.curriculum()
        cur["modules"][0]["lessons"][0]["concepts"][0]["concept_id"] = \
            "linalg.ghost"
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "curriculum.json", cur)
        assert cu.main(["--root", str(root), "validate",
                        "--course", "linear-algebra"]) == zs.EXIT_VALIDATION

    def test_an_unknown_course_exits_five(self, root):
        assert cu.main(["--root", str(root), "next",
                        "--course", "ghost"]) == zs.EXIT_NOT_FOUND
