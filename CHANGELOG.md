## [1.5.2] - 2025-12-30

### Added

* **Smart Update Checker**: The application now uses `packaging.version` to compare versions. It only notifies about updates if the remote version is strictly higher than the local one.
* **CI/CD Automation**: Added GitHub Action to automatically sync `VERSION` and `docker-compose.yml` image tags when a new Git tag (vX.Y.Z) is pushed.
* **Dynamic Docker Tags**: The `docker-compose.yml` now uses the `${APP_VERSION}` variable, allowing users to switch between releases easily.

### Changed

* **URL Normalization Fix**: Refined the normalization logic. The domain is still lowercased for deduplication, but the **Local Path** and **Query Parameters** now preserve their original case.

### Fixed

* **404 Errors**: Resolved an issue where URLs with case-sensitive paths (e.g., `/dDjpEn63`) failed because the entire URL was forced to lowercase.

## [1.5.1] - 2025-12-29

### Added

* **Input Deduplication**: Both standard and Multi-Geo checkers now filter out duplicate URLs and "Domain + Geo" pairs before starting the run.
* **Case-Insensitive Domain Matching**: Added logic to treat `Domain.com` and `domain.com` as the same entry to prevent redundant checks.

---

