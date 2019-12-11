# Changes

## v1.0.1

Bug fixes:

* Version ordering wasn't quite right for `1-a` vs `1.a` and `1-1` vs `1.1`.
* Fixed crash if versions compared included `cr` and `rc`, e.g. `1-rc1` vs `1-cr2`.
* Fixed a bug in URL artifact name examination.

Others:

* Increased unit test coverage.
* Added tools to help with scanning for broken POM or signatures.

## v1.0

Initial public release.
