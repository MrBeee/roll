Phase 0 fixture skeleton.

This directory is reserved for stable test data used by refactor-safety tests.

Suggested layout:
1. projects/ for .roll files and sidecar .npy/.ana.npy files.
2. wells/ for .well, .wws, .hdr, and related well inputs.
3. generated/ for test-created data that should not be committed.

Current Phase 0 tests generate their project files in temporary directories to keep the fixtures small.
