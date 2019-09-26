.PHONY: clean

BIN := bin
PROFILE := $(HOME)/.config/voice2json

all: model/trie

model/trie: model/alphabet.txt model/lm.binary model/clean-vocab.txt
	$(BIN)/generate_trie model/alphabet.txt model/lm.binary model/clean-vocab.txt $@

model/lm.binary: $(PROFILE)/language_model.txt
	$(BIN)/build_binary -T -s $< $@

model/clean-vocab.txt: $(PROFILE)/vocab.txt
	grep -vh '^[-<]' $< | awk '{print tolower($$0)}' | iconv -f utf8 -t ascii//TRANSLIT | sed -e "s/[^a-z']//g" > $@

clean:
	rm -f model/trie model/lm.binary model/clean-vocab.txt
