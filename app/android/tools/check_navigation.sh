#!/usr/bin/env sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_output=$(mktemp -d)
trap 'rm -rf "$test_output"' EXIT INT TERM
javac -d "$test_output" "$project_root/app/src/main/java/br/com/sistel/logsis/NavigationPolicy.java" "$project_root/tests/NavigationPolicyTest.java"
java -cp "$test_output" NavigationPolicyTest
