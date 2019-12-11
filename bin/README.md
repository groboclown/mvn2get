# About

Helper tools to work with `mvn2get`.

## POM Breakage

1. Pull down the sample POM files.  Tailing `/` is important on the URLs!
    ```bash
    mkdir /tmp/pom-search-dir
    cd /tmp/pom-search-dir
    search-for-poms.sh https://my.repo.name/sub/dir/
    ```
1. Scan those POM files for bad XML format.
    ```bash
    find-broken-xml.sh *.pom
    ```
