#!/usr/bin/env bash
num_jobs=10

parallel -k --pipe -n "${num_jobs}" \
         'voice2json transcribe-wav --stdin-files | voice2json recognize-intent'
