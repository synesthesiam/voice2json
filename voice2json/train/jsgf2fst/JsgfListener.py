#!/usr/bin/env python3
import re
import io
from typing import Optional


class JsgfListenerContext:
    def __init__(self, text: str, public: bool = False) -> None:
        self.text = text
        self.public = public

    def getText(self) -> str:
        return self.text

    def PUBLIC(self) -> bool:
        return self.public


# -----------------------------------------------------------------------------


class JsgfListener:
    EMPTY_CONTEXT = JsgfListenerContext("")

    GRAMMAR_DECLARATION = re.compile(r"^grammar ([^;]+);$")
    RULE_DEFINITION = re.compile(r"^(public)?\s*<([^>]+)>\s*=\s*([^;]+);$")

    def __init__(self, grammar: str) -> None:
        self._grammar = grammar

    def walk(self):
        """Processes grammar line-by-line. Executes enter/exit methods."""
        with io.StringIO(self._grammar) as grammar_file:
            for line in grammar_file:
                line = line.strip()
                if line.startswith("#") or (len(line) == 0):
                    continue

                grammar_match = JsgfListener.GRAMMAR_DECLARATION.match(line)
                if grammar_match is not None:
                    # grammar GrammarName;
                    grammar_name = grammar_match.group(1)
                    ctx = JsgfListenerContext(grammar_name)
                    self.enterGrammarName(ctx)
                    self.exitGrammarName(ctx)
                    self.enterGrammarBody(JsgfListener.EMPTY_CONTEXT)
                else:
                    # public <RuleName> = rule body;
                    # <RuleName> = rule body;
                    rule_match = JsgfListener.RULE_DEFINITION.match(line)
                    if rule_match is not None:
                        public = rule_match.group(1) is not None

                        # Rule definition
                        ctx = JsgfListenerContext("", public=public)
                        self.enterRuleDefinition(JsgfListener.EMPTY_CONTEXT)

                        # Rule name
                        rule_name = rule_match.group(2)
                        ctx = JsgfListenerContext(rule_name, public=public)
                        self.enterRuleName(ctx)
                        self.exitRuleName(ctx)

                        # Rule body
                        rule_text = rule_match.group(3)
                        self.enterRuleBody(JsgfListener.EMPTY_CONTEXT)

                        # Body expression
                        self.enterExpression(JsgfListener.EMPTY_CONTEXT)
                        self._walk_expression(rule_text)
                        self.exitExpression(JsgfListener.EMPTY_CONTEXT)

                        self.exitRuleBody(JsgfListener.EMPTY_CONTEXT)

                        # End rule
                        self.exitRuleDefinition(JsgfListener.EMPTY_CONTEXT)

            # Post-processing
            self.exitGrammarBody(JsgfListener.EMPTY_CONTEXT)

    # -------------------------------------------------------------------------

    def _walk_expression(
        self, text: str, end: Optional[str] = None, is_literal=True
    ) -> int:
        """Walks a full expression. Returns index in text where current expression ends."""
        next_index = 0
        literal = ""
        in_alternative = False

        # Process text character-by-character
        for current_index, c in enumerate(text):
            if current_index < next_index:
                # Skip ahread
                current_index += 1
                continue

            next_index = current_index + 1

            if c == end:
                # Found end character of expression (e.g., ])
                next_index += 1
                break
            elif c in ["<", "(", "[", "{", "|"]:
                # Begin group/tag/alt/etc.

                # Break literal here
                literal = literal.strip()
                if len(literal) > 0:
                    ctx = JsgfListenerContext(literal)
                    self.enterLiteral(ctx)
                    self.exitLiteral(ctx)
                    literal = ""

                if c == "<":
                    # Rule name
                    next_index = current_index + self._walk_expression(
                        text[current_index + 1 :], end=">", is_literal=False
                    )

                    # Include <>
                    rule_name = text[current_index:next_index]
                    ctx = JsgfListenerContext(rule_name)
                    self.enterRuleReference(ctx)
                    self.exitRuleReference(ctx)
                elif c == "(":
                    # Group (expression)
                    self.enterGroup(JsgfListener.EMPTY_CONTEXT)
                    self.enterExpression(JsgfListener.EMPTY_CONTEXT)
                    next_index = current_index + self._walk_expression(
                        text[current_index + 1 :], end=")"
                    )
                    self.exitExpression(JsgfListener.EMPTY_CONTEXT)
                    self.exitGroup(
                        JsgfListenerContext(text[current_index + 1 : next_index - 1])
                    )
                elif c == "[":
                    # Optional (expression)
                    self.enterOptional(JsgfListener.EMPTY_CONTEXT)
                    self.enterExpression(JsgfListener.EMPTY_CONTEXT)
                    next_index = current_index + self._walk_expression(
                        text[current_index + 1 :], end="]"
                    )
                    self.exitExpression(JsgfListener.EMPTY_CONTEXT)
                    self.exitOptional(JsgfListener.EMPTY_CONTEXT)
                elif c == "{":
                    # Tag bodies are *not* expressions
                    next_index = current_index + self._walk_expression(
                        text[current_index + 1 :], end="}", is_literal=False
                    )

                    # Exclude {}
                    tag_text = text[current_index + 1 : next_index - 1]
                    ctx = JsgfListenerContext(tag_text)
                    # self.enterExpression(JsgfListener.EMPTY_CONTEXT)
                    self.enterTagBody(ctx)
                    self.exitTagBody(ctx)
                    # self.exitExpression(JsgfListener.EMPTY_CONTEXT)
                elif c == "|":
                    if in_alternative:
                        # End previous alternative
                        self.exitAlternative(JsgfListener.EMPTY_CONTEXT)

                    # Begin next alternative
                    in_alternative = True
                    self.enterAlternative(JsgfListener.EMPTY_CONTEXT)
            else:
                # Accumulate into current literal
                literal += c

        # End of expression; Break literal.
        literal = literal.strip()
        if is_literal and (len(literal) > 0):
            ctx = JsgfListenerContext(literal)
            self.enterLiteral(ctx)
            self.exitLiteral(ctx)

        if in_alternative:
            # Close off alternative
            self.exitAlternative(JsgfListener.EMPTY_CONTEXT)

        return next_index

    # -------------------------------------------------------------------------

    def enterGrammarName(self, ctx: JsgfListenerContext):
        pass

    def exitGrammarName(self, ctx: JsgfListenerContext):
        pass

    def enterGrammarBody(self, ctx: JsgfListenerContext):
        pass

    def exitGrammarBody(self, ctx: JsgfListenerContext):
        pass

    def enterRuleDefinition(self, ctx: JsgfListenerContext):
        pass

    def exitRuleDefinition(self, ctx: JsgfListenerContext):
        pass

    def enterRuleName(self, ctx: JsgfListenerContext):
        pass

    def exitRuleName(self, ctx: JsgfListenerContext):
        pass

    def enterRuleBody(self, ctx: JsgfListenerContext):
        pass

    def exitRuleBody(self, ctx: JsgfListenerContext):
        pass

    def enterRuleReference(self, ctx: JsgfListenerContext):
        pass

    def exitRuleReference(self, ctx: JsgfListenerContext):
        pass

    def enterGroup(self, ctx: JsgfListenerContext):
        pass

    def exitGroup(self, ctx: JsgfListenerContext):
        pass

    def enterOptional(self, ctx: JsgfListenerContext):
        pass

    def exitOptional(self, ctx: JsgfListenerContext):
        pass

    def enterLiteral(self, ctx: JsgfListenerContext):
        pass

    def exitLiteral(self, ctx: JsgfListenerContext):
        pass

    def enterExpression(self, ctx: JsgfListenerContext):
        pass

    def exitExpression(self, ctx: JsgfListenerContext):
        pass

    def enterAlternative(self, ctx: JsgfListenerContext):
        pass

    def exitAlternative(self, ctx: JsgfListenerContext):
        pass

    def enterTagBody(self, ctx: JsgfListenerContext):
        pass

    def exitTagBody(self, ctx: JsgfListenerContext):
        pass

    def enterTag(self, ctx: JsgfListenerContext):
        pass

    def exitTag(self, ctx: JsgfListenerContext):
        pass
