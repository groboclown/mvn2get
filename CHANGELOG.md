# Changes

## v1.0.2

Bug fixes:

* Changed repository scan loop so that it only downloads from the first repository that contains the artifacts.  Before, the script would scan all the repositories for matching artifacts.
* Additional repository file list support, by looking for full URLs in the links.
* Ignores additional files ending with `.asc.asc`, `.md5.asc`, `.sha1.asc`, `.asc.asc.md5`, `asc.asc.sha1`, , `.md5.asc.md5`, `md5.asc.sha1`, , `.sha1.asc.md5`, and `sha1.asc.sha1`.


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
