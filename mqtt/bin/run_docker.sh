#!/usr/bin/env bash
docker run -it \
       -p 5000:5000 \
       -p 1994:1883 \
       -u "$(id -u):$(id -g)" \
       -e "HOME=$HOME" \
       -w "$(pwd)" \
       -v "${HOME}:${HOME}" \
       synesthesiam/voice2json-mqtt:amd64 "$@"
