#!/bin/bash

# Tool to search for broken POM files.

if [ -z "$1" -o "$1" == "-h" -o "$1" == "--help" ]; then
  echo "Usage: $0 (pom file) ..."
  echo "where each argument is a POM file."
  exit 1
fi

which xmllint > /dev/null 2>&1
if [ $? != 0 ]; then
  echo "You must install 'xmllit' (usually in the libxml2 or libxml2-utils package) to run this tool."
  exit 1
fi

tmp_out=/tmp/broken-pom-$$.txt
for f in "$@"; do
  xmllint --nonet --noout "$f" > /dev/null 2> "$tmp_out"
  if [ -s "$tmp_out" ] ; then
    echo "| $f | $tmp_out"
  fi
  rm "$tmp_out"
done
