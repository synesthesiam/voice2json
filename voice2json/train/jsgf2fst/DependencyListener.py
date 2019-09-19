import re
from collections import defaultdict
from typing import Optional, Dict, Set, List

import pywrapfst as fst
import networkx as nx

from .JsgfParserListener import JsgfParserListener

# -----------------------------------------------------------------------------

# Node Types:
# * local grammar
# * remote grammar
# * local rule
# * remote rule
# * slot


class DependencyListener(JsgfParserListener):
    def __init__(self, eps="<eps>"):
        # State
        self.grammar_name: Optional[str] = None
        self.in_rule: bool = False
        self.in_rule_reference: bool = False
        self.rule_name: Optional[str] = None
        self.reference_name: Optional[str] = None
        self.reference_grammar: Optional[str] = None
        self.tag_name: Optional[str] = None
        self.tag_substitution: Optional[str] = None
        self.literal_text: Optional[str] = None
        self.literal_words: List[Tuple[str, str]] = []

        # Directed graph with grammar/rule/slot dependencies
        self.graph = nx.DiGraph()

        # Symbol tables
        self.input_symbols = fst.SymbolTable()
        self.output_symbols = fst.SymbolTable()
        self.eps = eps

    # -------------------------------------------------------------------------

    def enterGrammarName(self, ctx):
        self.grammar_name = ctx.getText()
        self.graph.add_node(self.grammar_name, type="local grammar")

    def enterRuleBody(self, ctx):
        self.in_rule = True

    def exitRuleBody(self, ctx):
        self.in_rule = False

    # -------------------------------------------------------------------------
    # Rule References
    # -------------------------------------------------------------------------

    def enterRuleName(self, ctx):
        # Create qualified rule name
        self.rule_name = self.grammar_name + "." + ctx.getText()

        # Reference to rule in local grammar
        self.graph.add_node(self.rule_name, type="local rule")
        self.graph.add_edge(self.grammar_name, self.rule_name)

    def enterRuleReference(self, ctx):
        self.in_rule_reference = True

        # Strip <>
        self.reference_name = ctx.getText()[1:-1]

        # Check if name is fully qualified
        if "." not in self.reference_name:
            # Assume current grammar
            self.reference_name = self.grammar_name + "." + self.reference_name

            # Record reference to local rule
            self.graph.add_node(self.reference_name, type="local rule")

        # Get name of rule's grammar
        self.reference_grammar = self.reference_name.split(".", maxsplit=1)[0]

        if self.reference_grammar != self.grammar_name:
            # Record reference to other grammar
            self.graph.add_node(self.reference_grammar, type="remote grammar")
            self.graph.add_edge(self.grammar_name, self.reference_grammar)

            # Record reference to other grammar's rule
            self.graph.add_node(self.reference_name, type="remote rule")

        # Dependency edge
        self.graph.add_edge(self.rule_name, self.reference_name)

        # Add replacement symbol
        replace_symbol = "__replace__" + self.reference_name
        output_idx = self.output_symbols.add_symbol(replace_symbol)

    def exitRuleReference(self, ctx):
        self.in_rule_reference = False

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    def enterTagBody(self, ctx):
        self.tag_name = self._get_text(ctx)
        self.tag_substitution = None

        if ":" in self.tag_name:
            # Strip substitution out of tag name
            self.tag_name, self.tag_substitution = self.tag_name.split(":", maxsplit=1)

        # --[__begin__TAG]-->
        begin_symbol = "__begin__" + self.tag_name
        output_idx = self.output_symbols.add_symbol(begin_symbol)

        # --[__end__TAG]-->
        end_symbol = "__end__" + self.tag_name
        output_idx = self.output_symbols.add_symbol(end_symbol)

    def exitTagBody(self, ctx):
        self.tag_substitution = None

    # -------------------------------------------------------------------------
    # Literals
    # -------------------------------------------------------------------------

    def enterLiteral(self, ctx):
        if (not self.in_rule) or self.in_rule_reference:
            return

        literal_text = self._get_text(ctx)
        self.literal_words = []

        # Split words by whitespace
        for word in re.split(r"\s+", literal_text):
            if ":" in word:
                in_word = word.split(":", maxsplit=1)[0]

                # Empty input word becomes <eps>
                if len(in_word) == 0:
                    in_word = self.eps

                # NOTE: Entire word (with ":") is used as output
                out_word = word
            elif word.startswith("$"):
                # Record reference to slot (keep "$")
                self.graph.add_node(word, type="slot")
                self.graph.add_edge(self.rule_name, word)

                # Add replacement symbol
                replace_symbol = "__replace__" + word
                self.output_symbols.add_symbol(replace_symbol)

                in_word, out_word = replace_symbol, replace_symbol
            else:
                # Use word for both input and output
                in_word, out_word = word, word

            self.input_symbols.add_symbol(in_word)
            self.output_symbols.add_symbol(out_word)

            self.literal_words.append((in_word, out_word))

    # -------------------------------------------------------------------------

    def _get_text(self, ctx):
        # Get the original text *with* whitespace from ANTLR
        input_stream = ctx.start.getInputStream()
        start = ctx.start.start
        stop = ctx.stop.stop
        return input_stream.getText(start, stop)
