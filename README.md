# Maven 2 Artifact Downloader

Simple tool to get artifacts from Maven 2 repositories.

The tool will pull all the published files for the artifact and optionally pull the declared runtime dependencies.  It will also validate the checksums and PGP signatures.  It can also validate whether the declared license is one of a whitelisted set.

The tool is a single Python file that does not use external dependencies to operate.  It natively finds the resources and parses the POM files and verifies the downloaded files.  If you want to verify PGP signatures on the downloaded files, you will need to install the `gnupg` Python package.

Current version: [1.0](https://github.com/groboclown/mvn2get/releases/download/v1.0/mvn2get.py) ([changes](CHANGELOG.md))

## Usage

1. Make sure you have Python 3.7 or better installed.
1. (optional) Install `gnupg` to enable PGP signature validation.
    ```bash
    $ pip install gnupg
    ```
1. Download `mvn2get.py`
    ```bash
    $ wget https://github.com/groboclown/mvn2get/releases/download/v1.0/mvn2get.py
    $ chmod +x mvn2get.py
    ```
1. (optional) [Configure](#configuration) local settings.
    ```bash
    $ vi ~/.mvn2get.json
    ```
1. Download the artifact.
    ```bash
   $ mvn2get.py --resolve org.apache.logging.log4j:log4j-slf4j-impl:2.12.1
    ```

*Note* This tool currently only works for downloading from repositories that access groups with a `/` separator instead of a `.`. 

## Parameters

```
mvn2get.py [-h] [-d OUTPUT] [-r] [-O] [-v] [-p] [-P] [-e ERROR_FILE]
                  [-x] [-t] [--no-pgp] [--require-valid-license] []
                  [-c CONFIG_FILE]
                  artifact [artifact ...]
```

Most of these options can have a default value declared in the [configuration file](#configuration).

* **-h, --help**
    * Show the help.
* **-r, --resolve**
    * resolve the POM files and their dependencies, recursively.  Note that if the POM declares a dependency and it has already been downloaded, but that dependency's dependencies have not, then the recrusive dependencies are *not* downloaded.
* **-d OUTPUT, --dir OUTPUT**
    * directory to store the downloaded files (defaults to the current directory)
* **-O, --overwrite**
    * overwrite any already existing file with the same name
* **-v, --verbosity**
    * increase output verbosity.  Add additional `-v` arguments to make the program more verbose.
* **-p, --progress**
    * Show progress indicator
* **-P, --parent**
    * Download dependency management children (declared in parent and bom files).  Careful - this can download far more than you're expecting.  Note that if the parent has been downloaded, but its dependencies have not, then the dependencies are not downloaded.
* **-e ERROR_FILE, --error-file ERROR_FILE**
    * Add all discovered problems into the ERROR_FILE, for easier viewing or sending.
* **-x, --no-local**
    * Do not search local URLs for the dependency.  Without this, the tool will check the local repos list for existence of the artifact, and, if it exists, the dependency will not be downloaded.
* **-t, --no-remote-download**
    * Do not download files from the remote repo.  This will still discover the existence of the artifacts and find the dependencies.
* **--no-pgp**
    * Do not verify PGP signatures.
* **--require-valid-license**
    * Require that for all downloaded artifacts that define a license, it must be whitelisted.  If it does not have a license, then it is allowed.  Note that if you also specify `--require-license`, then all downloaded artifacts must have a whitelisted license.
* **--require-license**
    * Require that all downloaded artifacts must define a license name or URL.
* **-c CONFIG_FILE, --config CONFIG_FILE**
    * [configuration file](#configuration) to read default options from.  If not given, then the file `.mvn2get.json` in the current directory is loaded, and if that doesn't exist, the file `.mvn2get.json` in your home directory is loaded.
* **artifact**
    * 1 or more artifact specification to download.  These are either Maven-style URLs or gradle compact artifact notation (group:artifact:version).


## Configuration

You can have a configuration file in several ways:

1. First, if you specified the argument `--config`, then that filename is used as the configuration.
1. If that argument is not specified, but you have the file `.mvn2get.json` in the current working directory (the place where you ran the command), then that is loaded.
1. If you don't have any of the above configurations, but you have the file `$HOME/.mvn2get.json`, then that is loaded as the configuration.
1. Finally, anything you didn't specify in the configuration has the defaults used.


```javascript
{
  "show_progress": false,
  "log_level": "warn",
  "problem_file": "filename.txt", // default is `null`
  "recursive": false,
  "overwrite": false,
  "do_remote_download": true,
  "include_dep_management": false,
  "check_in_local": true,
  "no_pgp": false,
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
    // Many, many OSS licenses.
    // Does not include GPL licenses by default.
  ],
  "acceptable_license_names": [
    // Many, many OSS licenses.
    // Does not include GPL licenses by default.
  ],
  "allow_unacceptable_licenses": true,
  "allow_no_license": true,
  "mislabeled_artifact_groups": {
    "org.apache.felix.": ["org.apache.felix", ""],
    "org.osgi.": ["org.osgi", "org.osgi."],
    "wagon-http-shared": ["org.apache.maven.wagon", "wagon-http-shared"]
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
* `no_pgp` - if `true`, then downloaded artifact files do not have their PGP signatures checked.  This defaults to `false`, unless the `gnupg` package is not installed or the GnuPG binary can't be found.
* `progress_indicators` - a string of characters to prefix the progress, used as an ASCII spinner.
* `remote_repo_urls` - a list of URLs to search for the artifacts.
* `local_repo_urls` - a list of URLs to use when performing the `check_in_local` check.
* `pgp_key_servers` - a list of PGP key server URLs to look up the signing keys for artifact verification.  Only used if the Python module `gnupg` is installed.
* `acceptable_license_urls` - License URLs that are considered acceptable.  Compared against the POM license URL field.
* `acceptable_license_names` - License names that are considered acceptable.  If the POM license URL is not in the list or not given, then the logic checks if the name is a match.
* `allow_unacceptable_licenses` - If the declared POM license is not valid, and this is `false`, then the artifact is not downloaded.  Defaults to `true`.
* `allow_no_license` - If the POM does not declare a license and this is `false`, then the artifact is not downloaded.  Defaults to `true`.
* `mislabeled_artifact_groups` - In some cases, a POM mis-declares a dependency.  All artifact IDs that start with the key in this dictionary will have the group name replaced with the first value in the list, and the artifact ID will be prefixed with the second, and have the key prefix removed.

## Examples

### Download Dependencies That Are Not In Another Repo

Let's say we want to download `org.sonatype.goodies.dropwizard:dropwizard-support-core:1.0.3` and its dependencies from `jcenter`, but not those that are in `maven.org`.

Because this alters the list of repositories, this requires that the configuration file be used.  First, create a `mvn2get.json` file like so:

```json
{
  "local_repo_urls": ["https://repo1.maven.org/maven2/"],
  "remote_repo_urls": ["https://jcenter.bintray.com/"]
} 
```

Then run the command, specifying the configuration file:

```bash
mvn2get.py -r -p --config mvn2get.json org.sonatype.goodies.dropwizard:dropwizard-support-core:1.0.3
```


### Download Far Too Much

```bash
mvn2get.py -r -p --parent io.dropwizard:dropwizard-metrics-graphite:2.0.0
```


## Why Not Just Use Maven?

Unfortunately, the existing tools written in Java only pull down the jar files and sometimes the POM files.  Some of them, like using Maven itself, pollute the pulled down files with their own dependencies.


## License

[MIT](LICENSE)
