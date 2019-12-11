#!/bin/bash

# Tool to search for bad PGP signatures.

if [ -z "$1" -o "$1" == "-h" -o "$1" == "--help" ]; then
  echo "Usage: $0 (asc file) ..."
  echo "where each argument is a PGP signature file.  The corresponding file must also exist."
  exit 1
fi

which gpg2 > /dev/null 2>&1
if [ $? != 0 ]; then
  echo "You must install 'gpg' (usually in the gnupg or gnupg2 package) to run this tool."
  exit 1
fi

keyservers="--keyserver hkp://pool.sks-keyservers.net --keyserver hkps://hkps.pool.sks-keyservers.net"
gpgkeyring=".gpg-$$.kbx"
gpgcmd="gpg2 --no-default-keyring --keyring gpgkeyring $keyservers --auto-key-retrieve"
test -d "$gpghome" || mkdir -p "$gpghome"

tmp_out=/tmp/broken-pgp-$$.txt
for f in "$@"; do
  $gpgcmd --verify "$f" 2>/dev/null || echo "$f"
done
