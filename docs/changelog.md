# Changelog
<!--
SPDX-FileCopyrightText: 2026 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: CC0-1.0
-->

## 0.0.2: 'Reboot' (2026-04-16)

No new features are included in `0.0.2`; the main focus is tooling, packaging,
documentation, and maintainability.
The Python landscape has changed significantly since the initial release of this project
in 2023.
The setup, linting, build, and release workflows have been modernized so the project can
use current tool versions again.

A subsequent release should focus on incorporating pull-request contributions and new
features.

### Noteworthy changes

- The top-level package no longer re-exports `PySerialClientCommunicator`.
  Import it from `pykmp.client` instead:

    ```python
    from pykmp.client import PySerialClientCommunicator
    ```

- Documentation has expanded substantially.
  The project now has a MkDocs site with getting started, troubleshooting, practical
  hardware notes, API reference, contributing, and releasing documentation.
  Most of this documentation was already published soon after the 0.0.1 release in 2023.

### Development changes

- Development workflow has been modernized around `uv` and documented.
  Local setup, linting, building, and release instructions now use `uv`-managed
  environments and commands.
- Ruff has been updated from 0.0.292 to 0.15.11, along with the required configuration
  changes, updates to the `run-all-linters` script, and a few behavior-preserving code
  cleanups to satisfy newer lint rules.
- Formatting is now handled by `ruff format`, replacing Black in the repository tooling.
- Packaging and release instructions have been refreshed for the current toolchain,
  including local-first release guidance.

## 0.0.1: Initial release (2023-09-24)

Initial public release.
