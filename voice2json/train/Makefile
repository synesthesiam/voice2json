antlr_jar := "antlr/antlr-4.7.2-complete.jar"

antlr: JsgfLexer.g4 JsgfParser.g4
	java -jar $(antlr_jar) -Dlanguage=Python3 -o jsgf2fst/ $^
