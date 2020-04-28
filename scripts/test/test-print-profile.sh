#!/usr/bin/env bash
set -e

voice2json "$@" print-profile | jq . > /dev/null
