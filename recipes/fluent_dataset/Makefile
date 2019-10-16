.PHONY: clean
jobs := 10

all: results/report.json

results/report.json: results/intents.jsonl
	voice2json test-examples --expected results/test_truth.jsonl --actual $< | jq . > $@

results/intents.jsonl: results/transcriptions.jsonl
	voice2json recognize-intent < $< > $@

results/transcriptions.jsonl: test_files.txt
	cat $< | parallel -k --pipe -n $(jobs) \
		'voice2json transcribe-wav --stdin-files' > $@

clean:
	rm -f results/intents.jsonl results/transcriptions.jsonl
