parser grammar JsgfParser;

options { tokenVocab=JsgfLexer; }

r : grammarHeader grammarDeclaration grammarBody ;
grammarHeader : JSGF VERSION? encoding? language? SEMI ;
encoding : TOKEN+ ;
language : TOKEN+ ;

grammarDeclaration : GRAMMAR grammarName SEMI ;
grammarName : word ;
grammarBody : ruleDefinition+;

ruleDefinition : (PUBLIC)? LANGLE ruleName RANGLE EQUALS ruleBody SEMI ;
ruleName : TOKEN+ ;
ruleBody : expression ;

ruleReference : LANGLE literal RANGLE ;
atom : literal | ruleReference | group | optional ;
group : LPAREN expression+ RPAREN ;
optional : LBRACK expression+ RBRACK ;
literal : word+ ;
word : TOKEN+ ;
expression : atom (tag | expression | alternative)* ;
alternative : BAR expression ;
tagBody : (word | ESCAPE_LBRACE | ESCAPE_RBRACE)* ;
tag : LBRACE tagBody RBRACE ;