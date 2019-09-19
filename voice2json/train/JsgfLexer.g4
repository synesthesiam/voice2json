lexer grammar JsgfLexer;

// Keywords
PUBLIC : 'public' ;
JSGF : '#JSGF' ;
GRAMMAR : 'grammar' ;
VERSION : ('v' | 'V') Digit DOT Digit ;

// Separators
LPAREN : '(' ;
RPAREN : ')' ;
LBRACE : '{' ;
RBRACE : '}' ;
LBRACK : '[' ;
RBRACK : ']' ;
LANGLE : '<' ;
RANGLE : '>' ;
SEMI : ';' ;
DOT : '.' ;
HASH : '#' ;

// Operators
EQUALS : '=' ;
BAR : '|' ;

// Escape Sequences
ESCAPE_LBRACE : '\\{' ;
ESCAPE_RBRACE : '\\}' ;

// Whitespace and comments
WS : [ \t\r\n\u000C]+ -> channel(HIDDEN);
COMMENT : '/*' .*? '*/' -> channel(HIDDEN) ;
LINE_COMMENT : '//' ~[\r\n]* -> channel(HIDDEN) ;

TOKEN : ~(';' | '=' | '|' | '*' | '+' | '(' | ')'
          | '<' | '>' | '{' | '}' | '[' | ']'
          | ' ' | '\t' | '\r' | '\n' | '\u000C')+ ;

//IDENTIFIER : Letter LetterOrDigit* ;

//TOKEN : Letter LetterOrDigit* ;

fragment Digit : [0-9] ;
fragment LetterOrDigit : Letter | [0-9] ;
fragment Letter : [a-zA-Z$_]                          // letters below 0x7F
                  | ~[\u0000-\u007F\uD800-\uDBFF]     // characters above 0x7F that aren't surrogate
                  | [\uD800-\uDBFF] [\uDC00-\uDFFF] ; // UTF-16 surrogate pair encodings for U+10000 to U+10FFF
