# Maven 2 Artifact Downloader

Simple tool to get artifacts from Maven 2 repositories.

## Usage

1. Make sure you have Python 3.7 or better installed.
1. Download `m2get.py`
1. (optional) Configure local settings.
1. Download the artifact.


## Configuration

You can have a configuration file in several ways:

1. First, if you specified the argument `--config`, then that filename is used as the configuration.
1. If that argument is not specified, but you have the file `.m2-get.json` in the current working directory (the place where you ran the command), then that is loaded.
1. If you don't have any of the above configurations, but you have the file `$HOME/.m2-get.json`, then that is loaded as the configuration.
1. Finally, anything you didn't specify in the configuration has the defaults used.


```json
{
  "show_progress": false,
  "log_level": "warn",
  "problem_file": "filename.txt",
  "recursive": false,
  "overwrite": false,
  "do_remote_download": true,
  "include_dep_management": false,
  "check_in_local": true,
  "progress_indicators": "|/-\\",
  "remote_repo_urls": [
    "https://repo1.maven.org/maven2/",
    "https://www.mvnrepository.com/artifact/",
    "https://plugins.gradle.org/m2/"
  ],
  "local_repo_urls": [],
  "pgp_key_servers": [
    "hkp://pool.sks-keyservers.net",
    "hkps://hkps.pool.sks-keyservers.net"  
  ],
  "acceptable_license_urls": [
  
  ],
  "acceptable_license_names": [
  
  ],
  "allow_unacceptable_licenses": true,
  "allow_no_license": true,
  "mislabeled_artifact_groups": {
  
  }
}
```

* `log_level` - level of logging to report.  Default is `warn`.  Valid values are: `warn`, `info`, `debug`, `trace`.
* `show_progress` - whether to show the download progress.  Default is `false`.
* `problem_file` - file to send the problems to.  Default is not set, which means to not send the problems to a file.
* `recursive` - download any dependency declared in the POM file.  Defaults to `false`.
* `overwrite` - if a downloaded artifact already exists, overwrite it.  Defaults to `false`.
* `do_remote_download` - if `false`, then the tool just checks if the remote artifact exists, otherwise it downloads the file.  Defaults to `true`.
* `include_dep_management` - if `true`, then the declared parents' and BOM dependencies are also pulled down.  This can end up pulling down most of the Maven repository in some cases, so use with care.  Defaults to `false`.
* `check_in_local` - if `true` and local repositories are declared, then the file is downloaded only if it is not found in the local repositories.
* `progress_indicators` - a string of characters to prefix the progress, used as an ASCII spinner.
* `remote_repo_urls` - a list of URLs to search for the artifacts.
* `local_repo_urls` - a list of URLs to use when performing the `check_in_local` check.
* `pgp_key_servers` - a list of PGP key server URLs to look up the signing keys for artifact verification.  Only used if the Python module `gnupg` is installed.
* `acceptable_license_urls` - License URLs that are considered acceptable.  Compared against the POM license URL field.
* `acceptable_license_names` - License names that are considered acceptable.  If the POM license URL is not in the list or not given, then the logic checks if the name is a match.
* `allow_unacceptable_licenses` - If the declared POM license is not valid, and this is `false`, then the artifact is not downloaded.  Defaults to `true`.
* `allow_no_license` - If the POM does not declare a license and this is `false`, then the artifact is not downloaded.  Defaults to `true`.
* `mislabeled_artifact_groups` - In some cases, a POM mis-declares a dependency.  This mapping converts the 
