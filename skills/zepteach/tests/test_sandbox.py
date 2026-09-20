"""What ZepTeach may touch, and what it refuses to do.

None of this needs a second machine. The part that opens a connection is
thin; everything that has to be correct is here and is testable on one
laptop, which is also why it was written this way round.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sandbox as sb  # noqa: E402
import zt_state as zs  # noqa: E402

ALLOW = ["/home/u/workdir", "/scratch/u"]


def run(argv):
    try:
        return sb.main(argv)
    except SystemExit as exc:
        return exc.code


def refusal(fn):
    with pytest.raises(sb.Refused) as exc:
        fn()
    return exc.value


class TestPathsInside:
    def test_the_permitted_directory_itself(self):
        assert sb.check_path("/home/u/workdir", ALLOW) == "/home/u/workdir"

    def test_something_inside_it(self):
        assert sb.check_path("/home/u/workdir/run/in.txt", ALLOW) == \
            "/home/u/workdir/run/in.txt"

    def test_a_second_permitted_directory(self):
        assert sb.check_path("/scratch/u/tmp", ALLOW) == "/scratch/u/tmp"

    def test_a_harmless_dot_segment_is_reduced(self):
        assert sb.check_path("/home/u/workdir/./a/../b", ALLOW) == \
            "/home/u/workdir/b"


class TestPathsOutside:
    def test_a_sibling_that_shares_the_opening_characters(self):
        """The error this exists for. Comparing as strings,
        "/home/u/workdir-evil".startswith("/home/u/workdir") is true, and
        those are two unrelated directories. The comparison is made one path
        component at a time for this reason, and reading the code does not
        make the danger obvious, so the test says it."""
        r = refusal(lambda: sb.check_path("/home/u/workdir-evil", ALLOW))
        assert r.code == "SBX006"

    def test_a_sibling_file_with_a_shared_prefix(self):
        refusal(lambda: sb.check_path("/scratch/under", ALLOW))

    def test_climbing_out_with_dot_dot(self):
        r = refusal(lambda: sb.check_path(
            "/home/u/workdir/../../../etc/passwd", ALLOW))
        assert r.code == "SBX006"

    def test_climbing_out_while_looking_like_it_stays_in(self):
        refusal(lambda: sb.check_path(
            "/home/u/workdir/a/b/../../../secrets", ALLOW))

    def test_a_home_shortcut_means_a_different_place_per_user(self):
        r = refusal(lambda: sb.check_path("~/workdir", ALLOW))
        assert r.code == "SBX002"

    def test_a_relative_path_depends_on_where_the_command_started(self):
        r = refusal(lambda: sb.check_path("run/in.txt", ALLOW))
        assert r.code == "SBX005"

    def test_a_network_share(self):
        r = refusal(lambda: sb.check_path(r"\\server\share\x", ALLOW))
        assert r.code == "SBX004"

    def test_a_url_is_not_a_path(self):
        r = refusal(lambda: sb.check_path("https://example.com/x", ALLOW))
        assert r.code == "SBX003"

    def test_reading_is_refused_too(self):
        """A directory the learner did not mention is not ZepTeach's to look
        in, even without writing to it."""
        r = refusal(lambda: sb.check_path("/etc/passwd", ALLOW,
                                          purpose="read"))
        assert r.code == "SBX006"

    def test_an_empty_allowlist_permits_nothing(self):
        """A host with nothing listed is a host nothing may be done on.
        Defaulting the other way would turn a configuration mistake into an
        unrestricted one."""
        r = refusal(lambda: sb.check_path("/anywhere", []))
        assert r.code == "SBX001"

    def test_every_refusal_says_what_to_do_instead(self):
        """A refusal with no alternative gets worked around, and the
        workaround is worse than what was refused."""
        for bad in ("~/x", "rel/x", "/etc/passwd", r"\\s\x",
                    "http://x/y"):
            assert refusal(lambda b=bad: sb.check_path(b, ALLOW)).suggestion


class TestCommandsThatChangeTheEnvironment:
    @pytest.mark.parametrize("cmd", [
        "pip install numpy",
        "pip3 install -r requirements.txt",
        "python -m pip install anything",
        "conda install -c conda-forge something",
        "mamba env create -f env.yml",
        "apt-get install build-essential",
        "brew install anything",
        "module load compiler/2024",
        "npm install left-pad",
        "echo 'export X=1' >> ~/.bashrc",
        "export PATH=/opt/bin:$PATH",
        "chmod 777 /home/u/workdir",
        "sudo anything",
        "git config --global user.name x",
        "crontab -e",
        "rm -rf /",
    ])
    def test_it_is_refused(self, cmd):
        r = refusal(lambda: sb.check_command(cmd, ALLOW, timeout=60))
        assert r.code == "SBX010"

    def test_the_refusal_names_an_alternative(self):
        r = refusal(lambda: sb.check_command("pip install numpy", ALLOW,
                                             timeout=60))
        assert "let them install it" in r.suggestion

    def test_ordinary_work_is_allowed(self):
        for cmd in ("python analyse.py --in data.csv",
                    "./run.sh",
                    "grep -c pattern notes.txt"):
            assert sb.check_command(cmd, ALLOW, timeout=60)["allowed"]

    def test_an_argument_list_is_checked_the_same_way(self):
        refusal(lambda: sb.check_command(["pip", "install", "numpy"],
                                         ALLOW, timeout=60))


class TestTimeLimits:
    def test_a_command_with_no_limit_is_refused(self):
        r = refusal(lambda: sb.check_command("python x.py", ALLOW))
        assert r.code == "SBX011"

    def test_a_limit_beyond_what_is_sensible_is_refused(self):
        r = refusal(lambda: sb.check_command("python x.py", ALLOW,
                                             timeout=99999))
        assert r.code == "SBX012"
        assert "submitted as a job" in r.suggestion

    def test_zero_is_not_a_limit(self):
        refusal(lambda: sb.check_command("python x.py", ALLOW, timeout=0))


class TestAWholePieceOfWork:
    """A tool's invocation block, as recorded in a course's resources file.
    The same checks apply wherever the tool actually lives; the plugin holds
    no notion of kinds of place."""

    def host(self, **over):
        doc = {"workdir": "/home/u/workdir", "allowed_paths": ALLOW,
               "timeout_seconds": 300}
        doc.update(over)
        return doc

    def test_a_reasonable_job_is_allowed(self):
        out = sb.check_job({"command": "python run.py",
                            "paths": ["/home/u/workdir/in.txt"]},
                           self.host())
        assert out["allowed"]
        assert out["workdir"] == "/home/u/workdir"

    def test_a_job_writing_outside_the_permitted_area_is_refused(self):
        refusal(lambda: sb.check_job(
            {"command": "python run.py", "paths": ["/etc/hosts"]},
            self.host()))

    def test_a_job_working_outside_the_permitted_area_is_refused(self):
        refusal(lambda: sb.check_job(
            {"command": "python run.py", "workdir": "/tmp/elsewhere"},
            self.host()))

    def test_something_others_depend_on_needs_the_work_to_state_its_size(
            self):
        """Where nothing else rations a shared thing, the stated number is
        the only limit on one piece of work taking all of it."""
        r = refusal(lambda: sb.check_job(
            {"command": "python run.py"},
            self.host(shared_with_others=True, size_limit=4)))
        assert r.code == "SBX021"

    def test_the_limit_the_learner_set_is_enforced(self):
        r = refusal(lambda: sb.check_job(
            {"command": "python run.py", "cores": 64},
            self.host(shared_with_others=True, size_limit=4)))
        assert r.code == "SBX022"

    def test_within_the_agreed_size_is_fine(self):
        out = sb.check_job({"command": "python run.py", "cores": 4},
                           self.host(shared_with_others=True, size_limit=4))
        assert out["cores"] == 4

    def test_a_tool_on_this_very_machine_goes_through_the_same_checks(self):
        """One guard, applied wherever work runs. The rules do not soften
        because a tool happens to be on the machine running these scripts."""
        here = {"workdir": "/home/u/workdir",
                "allowed_paths": ["/home/u/workdir"],
                "timeout_seconds": 60}
        assert sb.check_job({"command": "python x.py"}, here)["allowed"]
        refusal(lambda: sb.check_job(
            {"command": "pip install x"}, here))


class TestCredentials:
    @pytest.mark.parametrize("text", [
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "sk-abcdefghijklmnopqrstuvwxyz0123",
        "password: hunter2",
        "TOKEN=ghp_somethinglong",
    ])
    def test_something_that_looks_like_a_credential_is_refused(self, text):
        r = refusal(lambda: sb.check_no_secret(text, "the host entry"))
        assert r.code == "SBX030"
        assert "name of an environment variable" in r.suggestion

    def test_ordinary_text_passes(self):
        sb.check_no_secret("/home/u/.ssh/id_ed25519", "key_file")
        sb.check_no_secret("ZEPTEACH_OCR_KEY", "api_key_env")

    def test_the_refusal_does_not_repeat_the_secret_back(self):
        """A refusal is printed, and printed things end up in transcripts and
        logs. Reporting that a credential was found must not be the thing
        that records it."""
        secret = "sk-abcdefghijklmnopqrstuvwxyz0123"
        r = refusal(lambda: sb.check_no_secret(secret, "the host entry"))
        assert secret not in r.message
        assert secret not in r.suggestion
        assert secret not in json.dumps(r.as_dict())


class TestCli:
    def test_a_permitted_path_exits_zero(self, capsys):
        assert run(["path", "/home/u/workdir/x",
                    "--allow", "/home/u/workdir"]) == zs.EXIT_OK

    def test_a_refused_path_exits_three_and_explains(self, capsys):
        code = run(["path", "/home/u/workdir-evil",
                    "--allow", "/home/u/workdir"])
        err = capsys.readouterr().err
        assert code == zs.EXIT_GATE
        assert "REFUSED [SBX006]" in err
        assert "instead:" in err

    def test_refusing_an_install_exits_three(self, capsys):
        code = run(["command", "pip install numpy", "--timeout", "60",
                    "--allow", "/home/u/workdir"])
        assert code == zs.EXIT_GATE
        assert "does not do without being told" in capsys.readouterr().err

    def test_the_rules_can_be_printed_on_their_own(self, capsys):
        """Explaining a refusal should say the same thing every time."""
        assert run(["rules"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "reads included" in out
        assert "no time limit" in out

    def test_json_output_carries_the_reason(self, capsys):
        run(["--json", "path", "/etc/passwd", "--allow", "/home/u/workdir"])
        doc = json.loads(capsys.readouterr().out)
        assert doc["allowed"] is False
        assert doc["code"] == "SBX006"
        assert doc["instead"]
