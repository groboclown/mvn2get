#!/bin/bash

# Simple script to search for pom files.

if [ -z "$1" -o "$1" == "-h" -o "$1" == "--help" ]; then
  echo "Usage: $0 (base url) ..."
  echo "Make sure the urls end in a /, or bad things will happen."
  exit 1
fi

which curl > /dev/null 2>&1
if [ $? != 0 ]; then
  echo "You must install 'curl' to run this tool."
  exit 1
fi


base_remaining=/tmp/remaining-$$-
test -f "${base_remaining}1" && rm "${base_remaining}1"
test -f "${base_remaining}2" && rm "${base_remaining}2"
tmpsfile=/tmp/search-$$.txt

# Fill up the initial list of URLs to search
for i in "$@" ; do
  echo "$i" >> "${base_remaining}1"
done

now=1
next=2
wait_time=2

while [ -s "${base_remaining}$now" ] ; do
  # Setup the loop.  This is a depth-first search.
  test -f "${base_remaining}$next" && rm "${base_remaining}$next"

  while read -u 10 baseurl ; do
    echo "Scanning $baseurl"
    curl -o "${tmpsfile}" -sqL "$baseurl"
    if [ $? -eq 0 -a -s "${tmpsfile}" ] ; then
      # Extract the URLs from the HREF
      # Add in the base URL, because these are expected to be relative URLs.
      # Some repos add a ':' at the start, so ignore those.

      # Get child directories.
      # We only care about directories (end in "/") for the remaining list.
      sed -n 's#.*href="\:*\([^"]*\).*#'"${baseurl}"'\1#p' "${tmpsfile}"| egrep "/$" | egrep -v "\\.\\./$" >> "${base_remaining}$next"

      # Get pom files
      for pom_name in $( sed -n 's#.*href="\:*\([^"]*\).*#\1#p' "${tmpsfile}" | egrep "\\.pom(\\.asc)?$" ) ; do
        if [ ! -f "$pom_name" ] ; then
          echo "Fetching pom $pom_name"
          curl -o "$pom_name" -sqL "${baseurl}${pom_name}"
        fi
      done

    else
      echo "- failed to download"
    fi

    sleep $wait_time
  done 10< "${base_remaining}$now"

  # Prepare the loop for the next iteration...
  pn=$now
  now=$next
  next=$pn
done

test -f "${base_remaining}1" && rm "${base_remaining}1"
test -f "${base_remaining}2" && rm "${base_remaining}2"
test -f "${tmpsfile}" && rm "${tmpsfile}"
