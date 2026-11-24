# Releasing

Aule's firmware has one version, in the root `CMakeLists.txt`:

```cmake
set(PROJECT_VER "0.0.1")  # x-aule-version
```

Never edit it by hand: `scripts/version.py` writes it. The build copies it into the
application descriptor, so nothing else in the repository holds it. On every pull request,
the `Cppcheck and build tooling` check runs `scripts/version.py check`, which fails when the
version and `CHANGELOG.md` disagree, and the tool's tests.

## Version rules

Semantic versioning, before 1.0:

- a breaking change (`!` after the type, or a `BREAKING CHANGE:` line in the description)
  bumps the minor;
- `feat` and `fix` bump the patch; other types appear in the changelog but bump nothing;
- 1.0.0 is a deliberate decision, never automatic.

A version is digits and dots only: `0.0.2`, never `0.0.2-dev` or `0.0.2+abc1234`. The device
compares versions as numbers, so a suffix would stop its updates. Updates also only go up, so
a device still on the inherited 2.6.0 never moves to 0.0.x by itself: reflash it by USB.

## Cutting a release

From `aule`, up to date with GitHub:

```sh
python3 scripts/version.py release --push
```

It reads the PR titles merged since the last `aule-v*` tag, picks the next version by the
rules above, writes it, adds its section at the top of `CHANGELOG.md`, and commits
`chore(release): X.Y.Z` on a new branch `release/X.Y.Z`. Then it pushes the branch and opens
the PR, with the section as its description. To reword a line, edit `CHANGELOG.md` on that
branch, not only the description: the GitHub Release takes its text from the file. To choose
the version, name it (`release 0.1.0`); without `--push`, it stops after the commit. `notes`
previews the section, and `next` the version.

Merge the release PR before any other. If another PR lands first, the tag would include a
change the section does not list: close the release PR, delete its branch and run the
command again.

## After the merge

The release PR changes `CMakeLists.txt` on `aule`, which starts the **Aule release** workflow
(`.github/workflows/aule-release.yml`). It checks the version again, and stops if
`aule-vX.Y.Z` already exists, so a re-run is harmless. Otherwise it builds `aule/aule-v0.2`
as `firmware.yml` does from the commit that set the version, tags that commit `aule-vX.Y.Z`,
and publishes a GitHub Release with that title, its changelog section as the body, and two
files: `aule-v0.2-X.Y.Z.bin` (the full flash image, written at offset 0x0) and `SHA256SUMS`.

It runs only in `meet-aule/aule-fw`, only from `aule`, one release at a time, with the
built-in `GITHUB_TOKEN`. If a run fails, run the workflow again from the Actions tab: it builds
and tags the same commit, even after other merges. If that commit itself cannot be built,
revert the release PR, merge the fix, and cut the release again.

Tags are `aule-v*` because xiaozhi already uses `v*`; upstream's `release.yml` and
`docs/releasing.md` describe xiaozhi's full-matrix release, which Aule does not use. The first
tag, `aule-v0.0.1`, comes from merging the change that added this file. The tools count from
the newest tag, so if you delete that release, keep its tag, and if the run is skipped, tag
that merge by hand: `git tag aule-v0.0.1 <its SHA> && git push origin aule-v0.0.1`.

## Where to see the running version

- The first line the firmware logs at boot, after ESP-IDF's own startup lines, which bug
  reports ask for: `Aule firmware 0.0.1 (0123456789ab) on aule-v0.2` (version, commit, board).
- The update check's report (`docs/ota.md`): `application.version` and `application.commit`.
- The update check's `User-Agent` header: `aule-v0.2/0.0.1`.

The commit is the first 12 characters of the git SHA. `scripts/build.py` passes it on every
run, from `AULE_COMMIT` (CI sets a pull request's head, or the release's commit), else the
builder image's `FIRMWARE_SOURCE_REVISION`, else `GITHUB_SHA`, else git. `idf.py` alone keeps
the last value it was given, or reports `unknown`.

This follows how Anthropic releases its SDKs: a single version source, a release PR, then a
tag and a GitHub Release from the changelog.
