"""A learner's records outlive the plugin, and must survive it changing.

The situation this was written for is concrete. Somebody studied for three
weeks. The plugin then gained a rule saying an attempt cannot be recorded
unless an explanation is on file - and none of their three weeks has one,
because the version that taught them did not record explanations.

Two ways to handle that are unacceptable and both are tempting. Refusing to
run throws away real work over a rule that did not exist when the work was
done. Quietly writing a placeholder explanation for each old concept makes
the check pass, and makes the records say something happened that nobody can
vouch for - which is precisely the kind of unsupported claim the rest of this
project exists to refuse.

So old concepts are exempted by name, in a file, with the reason, and they
stay visible. The rule applies in full from the upgrade onwards.
"""

import json

import pytest

import conftest as fx
import learner as ln
import migrate as mg
import route as rt
import teaching as tp
import zt_state as zs


def old_root(root):
    """A root as the previous version would have left it: concepts marked
    taught, attempts recorded, and no explanation anywhere."""
    fx.write_mastery(root, [
        fx.mastery(fx.EIGENVALUE, state="practiced"),
        fx.mastery(fx.EIGENVECTOR, state="introduced"),
    ])
    for row in ln.load_mastery(root):
        row["first_taught"] = "2026-09-01T09:00:00+00:00"
    return root


class TestAnOldRootIsRecognised:
    def test_check_says_what_is_outstanding(self, root, capsys):
        old_root(root)
        assert mg.main(["check", "--root", str(root)]) == zs.EXIT_GATE
        out = capsys.readouterr().out
        assert "written by an earlier version" in out
        assert "migrate.py apply" in out

    def test_it_names_the_concepts_and_the_cost(self, root):
        old_root(root)
        work = {w["id"]: w for w in mg.outstanding(root)}
        found = work[mg.TEACHING_EVIDENCE]
        assert fx.EIGENVALUE in found["concepts"]
        assert "lost" in found["cost"]

    def test_check_changes_nothing(self, root):
        old_root(root)
        before = sorted(p.name for p in (root / "learner").iterdir())
        mg.main(["check", "--root", str(root)])
        assert sorted(p.name for p in (root / "learner").iterdir()) == before
        assert mg.ledger(root) == []

    def test_an_empty_root_is_not_an_old_root(self, tmp_path, capsys):
        assert mg.main(["check", "--root", str(tmp_path)]) == zs.EXIT_OK
        assert "nothing to upgrade" in capsys.readouterr().out

    def test_a_brand_new_learner_never_sees_an_upgrade_notice(self, tmp_path):
        """Caught by running it rather than by reasoning about it: the first
        thing a new learner saw was a paragraph about records written by an
        earlier version, of which they had none. A step with nothing to
        migrate and nothing to ask is already satisfied."""
        assert mg.outstanding(tmp_path) == []
        assert rt.next_step(tmp_path)["do"] == "setup1"

    def test_a_set_up_learner_with_no_history_is_also_left_alone(self, root):
        """The fixture root has config and a profile and no mastery rows.
        Nothing has been taught, so nothing predates the rule."""
        assert [w["id"] for w in mg.outstanding(root)] == [mg.NOTATION]


class TestApplyingIt:
    def test_a_copy_is_taken_before_anything_is_touched(self, root):
        old_root(root)
        assert mg.main(["apply", "--root", str(root)]) == zs.EXIT_OK
        backups = list((root / ".backups").iterdir())
        assert len(backups) == 1
        assert (backups[0] / "learner" / "mastery.jsonl").exists()

    def test_old_concepts_are_exempted_by_name_not_back_filled(self, root):
        old_root(root)
        mg.main(["apply", "--root", str(root)])

        # exempt, and recorded as exempt
        assert fx.EIGENVALUE in mg.grandfathered(root)
        doc = zs.read_json(root / mg.GRANDFATHERED)
        assert "not because anything is known" in doc["why"]

        # and emphatically NOT given an explanation nobody wrote
        assert ln.load_expositions(root) == []

    def test_running_it_twice_changes_nothing_the_second_time(self, root):
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        first = zs.read_json(root / mg.GRANDFATHERED)
        assert mg.main(["apply", "--root", str(root)]) == zs.EXIT_OK
        assert zs.read_json(root / mg.GRANDFATHERED) == first
        assert len(mg.ledger(root)) == len(mg.STEPS)

    def test_afterwards_the_root_reports_as_up_to_date(self, root, capsys):
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        capsys.readouterr()
        assert mg.main(["check", "--root", str(root)]) == zs.EXIT_OK
        assert "up to date" in capsys.readouterr().out

    def test_steps_are_keyed_by_name_so_a_later_one_can_be_inserted(self,
                                                                   root):
        """Numbering them is how a root skips a step forever: it has run to
        4, a 3b is added, and it never looks back. The ledger records which
        steps ran, so anything not in it is applied whenever it appears."""
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        assert mg.applied(root) == {s["id"] for s in mg.STEPS}

        mg.STEPS.append({"id": "invented-later", "title": "t",
                         "needed": lambda r: {"step": "invented-later",
                                              "concepts": ["some.concept"]},
                         "apply": lambda r, w: {"did": "something"}})
        try:
            assert [w["id"] for w in mg.outstanding(root)] == \
                ["invented-later"]
            mg.main(["apply", "--root", str(root)])
            assert "invented-later" in mg.applied(root)
        finally:
            mg.STEPS.pop()


class TestStudyCarriesOnAfterwards:
    def test_an_old_concept_can_be_practised_again(self, root):
        """The point of the whole exercise. Three weeks of study is not
        thrown away by a rule that arrived afterwards."""
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.attempt(
                            submitted_at="2026-09-20T10:00:00+00:00"))])
        assert code == zs.EXIT_OK

    def test_without_the_upgrade_that_same_attempt_is_refused(self, root):
        old_root(root)
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.attempt())])
        assert code == zs.EXIT_GATE

    def test_a_concept_taught_after_the_upgrade_gets_no_exemption(self, root):
        """The exemption is for records that predate the rule, and it must
        not become a hole that new work falls through."""
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        new_concept = fx.SHARED
        assert new_concept not in mg.grandfathered(root)
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.attempt(attempt_id="a2",
                                              concept_ids=[new_concept]))])
        assert code == zs.EXIT_GATE

    def test_the_exemption_list_stays_visible(self, root):
        """So that it does not quietly become permanent. If one of these
        turns out to be shaky, re-teaching it is the repair and that
        re-teaching is recorded properly."""
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        doc = zs.read_json(root / mg.GRANDFATHERED)
        assert set(doc["concepts"]) == {fx.EIGENVALUE, fx.EIGENVECTOR}
        assert doc["concepts"][fx.EIGENVALUE]["first_taught"]


class TestTheQuestionNobodyCanMigrate:
    def test_the_notation_channel_is_reported_as_still_to_ask(self, root):
        old_root(root)
        work = {w["id"]: w for w in mg.outstanding(root)}
        assert "how do you want to give it" in work[mg.NOTATION]["ask"]

    def test_applying_it_invents_no_answer(self, root):
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        profile = zs.read_json(root / "learner" / "profile.json")
        assert "notation_input" not in profile, (
            "guessing would be worse than leaving it open: it would look "
            "like the learner had said something")


class TestTheLearnerIsToldBeforeItMatters:
    def test_the_router_puts_the_upgrade_before_everything_else(self, root):
        """It has to arrive through the routing entry point, because that is
        the one thing every host reads. Anything that only lives in the
        slash commands never reaches Codex, which loads SKILL.md and the
        scripts and nothing else."""
        old_root(root)
        step = rt.next_step(root)
        assert step["do"] == "upgrade"
        assert "migrate.py check" in " ".join(step["run"])

    def test_it_says_the_work_is_not_lost(self, root):
        old_root(root)
        assert "都在" in rt.next_step(root)["say"]

    def test_once_applied_the_router_moves_on(self, root):
        old_root(root)
        mg.main(["apply", "--root", str(root)])
        assert rt.next_step(root)["do"] != "upgrade"

    def test_the_upgrade_is_a_real_route(self, root):
        res = rt.resolve("upgrade", root)
        assert res["missing"] == []
        assert any("migrate.py" in r for r in res["run"])
