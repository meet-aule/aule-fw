"""Follow the commit from scripts/build.py through CMake into the boot log and the update check.

ESP-IDF is not needed: the CMake block and the C++ statements run in small host programs.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build)

SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"


def git_result(returncode, stdout):
    return subprocess.CompletedProcess(["git", "rev-parse", "HEAD"], returncode, stdout, "")


def commit_variables(**values):
    """Set the variables build.py reads the commit from; any not given is empty.

    CI sets GITHUB_SHA and the firmware builder image sets FIRMWARE_SOURCE_REVISION, so each
    test replaces all of them.
    """
    return mock.patch.dict(
        os.environ, {name: values.get(name, "") for name in build._GIT_SHA_VARIABLES}
    )


class BuildScriptTests(unittest.TestCase):
    def test_ci_builds_use_github_sha(self):
        with (
            commit_variables(GITHUB_SHA=SHA),
            mock.patch.object(build.subprocess, "run") as run,
        ):
            self.assertEqual(build._get_git_sha(), "0123456789ab")
        run.assert_not_called()

    def test_the_most_explicit_commit_wins(self):
        cases = [
            ("AULE_COMMIT first",
             {"AULE_COMMIT": SHA, "FIRMWARE_SOURCE_REVISION": OTHER_SHA, "GITHUB_SHA": OTHER_SHA}),
            ("then the builder image's revision",
             {"FIRMWARE_SOURCE_REVISION": SHA, "GITHUB_SHA": OTHER_SHA}),
            ("the image's default 'unknown' is skipped",
             {"AULE_COMMIT": "unknown", "FIRMWARE_SOURCE_REVISION": "unknown", "GITHUB_SHA": SHA}),
            ("12 characters are enough", {"AULE_COMMIT": SHA[:12]}),
            ("case and spaces do not matter", {"AULE_COMMIT": f" {SHA.upper()}\n"}),
        ]
        for name, values in cases:
            with (
                self.subTest(name),
                commit_variables(**values),
                mock.patch.object(build.subprocess, "run") as run,
            ):
                self.assertEqual(build._get_git_sha(), "0123456789ab")
                run.assert_not_called()

    def test_other_builds_ask_git(self):
        git = git_result(0, SHA + "\n")
        with (
            commit_variables(),
            mock.patch.object(build.subprocess, "run", return_value=git) as run,
        ):
            self.assertEqual(build._get_git_sha(), "0123456789ab")
        self.assertEqual(run.call_args.args[0], ["git", "rev-parse", "HEAD"])

    def test_unknown_when_no_commit_can_be_read(self):
        with commit_variables():
            for name, outcome in (
                ("git refuses", {"return_value": git_result(128, "")}),
                ("git prints something else", {"return_value": git_result(0, "HEAD\n")}),
                ("git is missing", {"side_effect": FileNotFoundError("git")}),
            ):
                with self.subTest(name), mock.patch.object(build.subprocess, "run", **outcome):
                    self.assertEqual(build._get_git_sha(), "unknown")

    def test_a_malformed_value_never_reaches_the_build(self):
        for name in build._GIT_SHA_VARIABLES:
            for value in ('abc"; rm -rf /', "0123456", "0123456789ag"):
                with (
                    self.subTest(name=name, value=value),
                    commit_variables(**{name: value}),
                    mock.patch.object(build.subprocess, "run", return_value=git_result(0, SHA)),
                ):
                    self.assertEqual(build._get_git_sha(), "0123456789ab")


class WorkflowTests(unittest.TestCase):
    def test_pull_request_builds_report_their_head(self):
        workflow = (ROOT / ".github/workflows/firmware.yml").read_text(encoding="utf-8")
        # Set for the whole job, so the build and the artifact's name use the same commit.
        job = workflow[workflow.index("\n  build:\n"):workflow.index("\n    steps:\n")]
        self.assertIn("AULE_COMMIT: ${{ github.event.pull_request.head.sha || github.sha }}", job)
        self.assertIn('_${AULE_COMMIT::7}" >> "$GITHUB_OUTPUT"', workflow)
        self.assertNotIn("GITHUB_SHA", workflow)


@unittest.skipUnless(shutil.which("cmake") and shutil.which("c++"),
                     "requires CMake and a host C++ compiler")
class CMakeTests(unittest.TestCase):
    """Run main/CMakeLists.txt's commit block in a small host project."""

    @classmethod
    def setUpClass(cls):
        cmake = (ROOT / "main/CMakeLists.txt").read_text(encoding="utf-8")
        start = cmake.index("# The commit the firmware is built from.")
        block = cmake[start:cmake.index("\nendif()\n", start) + len("\nendif()\n")]
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.source = Path(cls.directory.name) / "source"
        cls.source.mkdir()
        for name in ("aule_git_sha.h", "aule_git_sha.cc.in"):
            shutil.copy(ROOT / "main" / name, cls.source / name)
        (cls.source / "other.cc").write_text("int Other() { return 1; }\n", encoding="utf-8")
        (cls.source / "print_sha.cc").write_text(
            '#include <cstdio>\n#include "aule_git_sha.h"\n'
            "int main() { std::puts(kAuleGitSha); }\n",
            encoding="utf-8",
        )
        (cls.source / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\n"
            "project(commit_test CXX)\n"
            "# Stands in for the library idf_component_register creates for main.\n"
            "add_library(main STATIC other.cc)\n"
            "target_include_directories(main PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})\n"
            "set(COMPONENT_LIB main)\n"
            + block
            + "add_executable(print_sha print_sha.cc)\n"
            "target_link_libraries(print_sha main)\n",
            encoding="utf-8",
        )

    def setUp(self):
        self.binary = Path(self.directory.name) / self._testMethodName

    def configure(self, *definitions):
        """Configure, and return the source file CMake generated for the commit."""
        command = ["cmake", "-S", str(self.source), "-B", str(self.binary), *definitions]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.binary / "aule_git_sha.cc").read_text(encoding="utf-8")

    def build_and_run(self):
        result = subprocess.run(["cmake", "--build", str(self.binary)], capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return subprocess.run([str(self.binary / "print_sha")], capture_output=True,
                              text=True, check=True).stdout.strip()

    def test_a_new_commit_rebuilds_only_its_own_file(self):
        self.configure("-DAULE_GIT_SHA=0123456789ab")
        self.assertEqual(self.build_and_run(), "0123456789ab")
        other = next(self.binary.rglob("other.cc.o"))
        compiled = other.stat().st_mtime_ns
        # Make may compare whole seconds, so let the regenerated file be visibly newer.
        time.sleep(1.1)

        self.configure("-DAULE_GIT_SHA=ba9876543210")
        self.assertEqual(self.build_and_run(), "ba9876543210")
        self.assertEqual(other.stat().st_mtime_ns, compiled)

    def test_anything_but_12_hex_digits_is_unknown(self):
        self.assertIn('kAuleGitSha[] = "0123456789ab";',
                      self.configure("-DAULE_GIT_SHA=0123456789ab"))
        for value in ("0123456789a", "0123456789abc", "0123456789AB", 'abc"ef012345', ""):
            with self.subTest(value=value):
                self.assertIn('kAuleGitSha[] = "unknown";',
                              self.configure(f"-DAULE_GIT_SHA={value}"))
        self.assertIn('kAuleGitSha[] = "unknown";', self.configure("-UAULE_GIT_SHA"))


def compile_and_run(test, sources, flags=()):
    """Build host C++ sources (name to text) with main/ on the include path; return stdout."""
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for name, text in sources.items():
            paths.append(Path(directory) / name)
            paths[-1].write_text(text, encoding="utf-8")
        binary = Path(directory) / "program"
        result = subprocess.run(
            ["c++", "-std=c++17", "-Wall", "-Wextra", *flags, "-I", str(ROOT / "main"),
             *map(str, paths), "-o", str(binary)],
            capture_output=True, text=True,
        )
        test.assertEqual(result.returncode, 0, result.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, check=True).stdout


def generated_sha_source(sha):
    """What CMake's configure_file writes from the template."""
    template = (ROOT / "main/aule_git_sha.cc.in").read_text(encoding="utf-8")
    return template.replace("@AULE_GIT_SHA@", sha)


@unittest.skipUnless(shutil.which("c++"), "requires a host C++ compiler")
class BootLogTests(unittest.TestCase):
    def test_first_line_names_the_version_commit_and_board(self):
        source = (ROOT / "main/main.cc").read_text(encoding="utf-8")
        body = source[source.index("void app_main(void)"):]
        start = body.index('ESP_LOGI(TAG, "Aule firmware')
        # Only comments come before it in app_main, so nothing can fail first.
        before = body[body.index("{") + 1:start].splitlines()
        self.assertTrue(all(not line.strip() or line.strip().startswith("//") for line in before))
        statement = body[start:body.index(";", start) + 1]

        output = compile_and_run(self, {
            "aule_git_sha.cc": generated_sha_source("0123456789ab"),
            "boot.cc": textwrap.dedent("""\
                #include <cstdio>
                #include "aule_git_sha.h"
                #define TAG "main"
                #define BOARD_NAME "aule-v0.2"
                #define ESP_LOGI(tag, format, ...) std::printf(format "\\n", __VA_ARGS__)
                struct esp_app_desc_t { char version[32]; };
                const esp_app_desc_t* esp_app_get_description() {
                    static const esp_app_desc_t description = {"0.0.1"};
                    return &description;
                }
                int main() {
                """) + statement + "\n}\n",
        }, flags=["-Werror"])
        self.assertEqual(output, "Aule firmware 0.0.1 (0123456789ab) on aule-v0.2\n")


@unittest.skipUnless(shutil.which("c++"), "requires a host C++ compiler")
class CheckInTests(unittest.TestCase):
    def application(self, sha):
        source = (ROOT / "main/boards/common/board.cc").read_text(encoding="utf-8")
        start = source.index("    auto app_desc = esp_app_get_description();")
        block = source[start:source.index('    json += R"("partition_table": [)";', start)]
        output = compile_and_run(self, {
            "aule_git_sha.cc": generated_sha_source(sha),
            "report.cc": textwrap.dedent("""\
                #include <cstdio>
                #include <iostream>
                #include <string>
                #include "aule_git_sha.h"
                struct esp_app_desc_t {
                    char version[32], project_name[32], time[16], date[16], idf_ver[32];
                    unsigned char app_elf_sha256[32];
                };
                const esp_app_desc_t* esp_app_get_description() {
                    static const esp_app_desc_t description = {
                        "0.0.1", "xiaozhi", "12:00:00", "Nov 24 2026", "v6.1", {0xab}};
                    return &description;
                }
                int main() {
                    std::string json = "{";
                """) + block + textwrap.dedent("""\
                    json.back() = '}';  // The block ends with "}," before the next property.
                    std::cout << json;
                }
                """),
        })
        return json.loads(output)["application"]

    def test_report_adds_the_commit_and_keeps_the_version(self):
        application = self.application("0123456789ab")
        self.assertEqual(
            list(application),
            ["name", "version", "compile_time", "idf_version", "elf_sha256", "commit"],
        )
        self.assertEqual(application["commit"], "0123456789ab")
        self.assertEqual(application["version"], "0.0.1")
        self.assertEqual(application["name"], "xiaozhi")
        self.assertEqual(application["elf_sha256"], "ab" + "00" * 31)

    def test_report_for_an_unknown_commit(self):
        self.assertEqual(self.application("unknown")["commit"], "unknown")


if __name__ == "__main__":
    unittest.main()
