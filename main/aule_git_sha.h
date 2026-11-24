#ifndef _AULE_GIT_SHA_H_
#define _AULE_GIT_SHA_H_

// The commit this firmware was built from: the first 12 characters of its git SHA, or
// "unknown". main/CMakeLists.txt writes it into aule_git_sha.cc from the value scripts/build.py
// passes, so a new commit recompiles that one file. It is reported next to PROJECT_VER and never
// inside it, because the update check compares versions as numbers.
extern const char kAuleGitSha[];

#endif  // _AULE_GIT_SHA_H_
