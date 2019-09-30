import re
import logging
from collections import defaultdict, deque
from typing import Optional, Dict, Set, List

logger = logging.getLogger("FSTListener")

import pywrapfst as fst

from .DependencyListener import DependencyListener

# -----------------------------------------------------------------------------


class FSTListener(DependencyListener):
    def __init__(self, grammar: str, eps: str = "<eps>"):
        super().__init__(grammar)

        self.input_symbols.add_symbol(eps)
        self.output_symbols.add_symbol(eps)

        # Grammar name
        self.grammar_name: Optional[str] = None

        # State
        self.is_public: bool = False
        self.in_rule: bool = False
        self.in_rule_reference: bool = False
        self.rule_name: bool = None

        # Nesting level of groups/optionals
        self.group_depth: int = 0

        # rule name -> state index
        self.last_states: Dict[str, int] = {}

        # group depth -> state index
        self.opt_states: Dict[int, int] = {}
        self.alt_states: Dict[int, int] = {}
        self.alt_ends: Dict[int, int] = {}
        self.tag_states: Dict[int, int] = {}
        self.exp_states: Dict[int, int] = {}

        # FST
        self.grammar_fst: Optional[fst.Fst] = None
        self.fst: Optional[fst.Fst] = None
        self.fsts: Dict[str, fst.Fst] = {}

        # Cached weight
        self.weight_one: Optional[fst.Weight] = None

        # Indices of <eps> tokens
        self.in_eps: int = self.input_symbols.find(eps)
        self.out_eps: int = self.output_symbols.find(eps)

    # -------------------------------------------------------------------------

    def exitGrammarBody(self, ctx):
        # Fix symbol tables
        for rule_fst in self.fsts.values():
            rule_fst.set_input_symbols(self.input_symbols)
            rule_fst.set_output_symbols(self.output_symbols)

    # -------------------------------------------------------------------------

    def enterGrammarName(self, ctx):
        super().enterGrammarName(ctx)

    def enterRuleDefinition(self, ctx):
        # Only a single public rule is expected
        self.is_public = ctx.PUBLIC() is not None

    def exitRuleDefinition(self, ctx):
        self.is_public = False
        self.fst.set_final(self.last_states[self.rule_name])

    def enterRuleName(self, ctx):
        super().enterRuleName(ctx)

    def enterRuleBody(self, ctx):
        super().enterRuleBody(ctx)

        # Create new FST for rule
        self.fst = fst.Fst()
        self.start_state = self.fst.add_state()
        self.fst.set_start(self.start_state)
        self.last_states[self.rule_name] = self.start_state
        self.weight_one = fst.Weight.One(self.fst.weight_type())

        if self.is_public:
            # Check if this is the main rule of the grammar
            grammar_rule = self.grammar_name + "." + self.grammar_name
            if self.rule_name == grammar_rule:
                self.grammar_fst = self.fst

        # Cache FST
        self.fsts[self.rule_name] = self.fst

        # Reset state
        self.group_depth = 0
        self.opt_states = {}
        self.alt_states = {}
        self.tag_states = {}
        self.exp_states = {}
        self.alt_ends = {}

        # Save anchor state
        self.alt_states[self.group_depth] = self.last_states[self.rule_name]

    def enterExpression(self, ctx):
        self.exp_states[self.group_depth] = self.last_states[self.rule_name]

    # -------------------------------------------------------------------------
    # Groups/Optionals
    # -------------------------------------------------------------------------

    def enterAlternative(self, ctx):
        anchor_state = self.alt_states[self.group_depth]

        if self.group_depth not in self.alt_ends:
            # Patch start of alternative
            next_state = self.fst.add_state()
            for arc in self.fst.arcs(anchor_state):
                self.fst.add_arc(next_state, arc)

            self.fst.delete_arcs(anchor_state)
            self.fst.add_arc(
                anchor_state,
                fst.Arc(self.in_eps, self.out_eps, self.weight_one, next_state),
            )

            # Create shared end state for alternatives
            self.alt_ends[self.group_depth] = self.fst.add_state()

        # Close previous alternative
        last_state = self.last_states[self.rule_name]
        end_state = self.alt_ends[self.group_depth]
        if last_state != end_state:
            self.fst.add_arc(
                last_state,
                fst.Arc(self.in_eps, self.out_eps, self.weight_one, end_state),
            )

        # Add new intermediary state
        next_state = self.fst.add_state()
        self.fst.add_arc(
            anchor_state,
            fst.Arc(self.in_eps, self.out_eps, self.weight_one, next_state),
        )
        self.last_states[self.rule_name] = next_state

    def exitAlternative(self, ctx):
        # Create arc to shared end state
        last_state = self.last_states[self.rule_name]
        end_state = self.alt_ends[self.group_depth]
        if last_state != end_state:
            self.fst.add_arc(
                last_state,
                fst.Arc(self.in_eps, self.out_eps, self.weight_one, end_state),
            )

        self.last_states[self.rule_name] = end_state

    def enterOptional(self, ctx):
        # Save anchor state
        self.opt_states[self.group_depth] = self.last_states[self.rule_name]

        # Optionals are honorary groups
        self.group_depth += 1

        # Save anchor state
        self.alt_states[self.group_depth] = self.last_states[self.rule_name]

    def exitOptional(self, ctx):
        # Optionals are honorary groups
        self.alt_ends.pop(self.group_depth, None)
        self.group_depth -= 1

        anchor_state = self.opt_states[self.group_depth]
        last_state = self.last_states[self.rule_name]

        # Add optional by-pass arc
        # --[<eps>]-->
        self.fst.add_arc(
            anchor_state,
            fst.Arc(self.in_eps, self.out_eps, self.weight_one, last_state),
        )

    def enterGroup(self, ctx):
        # Critical for tags to work.
        # Need to keep track of the adjacent expression, whether or not it's
        # inside a group.
        # So text{tag} and (text){tag} both work.
        self.exp_states[self.group_depth] = self.last_states[self.rule_name]

        self.group_depth += 1

        # Save anchor state for alternatives
        self.alt_states[self.group_depth] = self.last_states[self.rule_name]

    def exitGroup(self, ctx):
        # Clear end state for alternatives
        self.alt_ends.pop(self.group_depth, None)
        self.group_depth -= 1

    # -------------------------------------------------------------------------
    # Rule References
    # -------------------------------------------------------------------------

    def enterRuleReference(self, ctx):
        super().enterRuleReference(ctx)

        # Create transition that will be replaced with a different FST
        replace_symbol = "__replace__" + self.reference_name
        output_idx = self.output_symbols.find(replace_symbol)

        # --[__replace__RULE]-->
        last_state = self.last_states[self.rule_name]
        next_state = self.fst.add_state()
        self.fst.add_arc(
            last_state, fst.Arc(self.in_eps, output_idx, self.weight_one, next_state)
        )
        self.last_states[self.rule_name] = next_state

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    def enterTagBody(self, ctx):
        super().enterTagBody(ctx)

        # Patch start of tag
        anchor_state = self.exp_states[self.group_depth]
        next_state = self.fst.add_state()

        # --[__begin__TAG]-->
        begin_symbol = "__begin__" + self.tag_name
        output_idx = self.output_symbols.find(begin_symbol)
        assert output_idx >= 0, f"{begin_symbol} not found"

        # Move outgoing anchor arcs
        for arc in self.fst.arcs(anchor_state):
            self.fst.add_arc(
                next_state, fst.Arc(arc.ilabel, arc.olabel, arc.weight, arc.nextstate)
            )

        # Patch all words inside the tag if there will be a substitution
        if self.tag_substitution is not None:
            state_queue = deque([next_state])
            while len(state_queue) > 0:
                state = state_queue.popleft()
                mutable_arcs = self.fst.mutable_arcs(state)

                # Modify arcs in-place
                while not mutable_arcs.done():
                    arc = mutable_arcs.value()

                    # Create "WORD:" that will never output anything.
                    # Substitution token is added later below.
                    output_symbol = self.output_symbols.find(arc.olabel).decode()
                    arc.olabel = self.output_symbols.add_symbol(output_symbol + ":")
                    state_queue.append(arc.nextstate)

                    # Update arc in-place
                    mutable_arcs.set_value(arc)
                    mutable_arcs.next()

        # Patch anchor
        self.fst.delete_arcs(anchor_state)
        self.fst.add_arc(
            anchor_state, fst.Arc(self.in_eps, output_idx, self.weight_one, next_state)
        )

        # Patch end of tag
        last_state = self.last_states[self.rule_name]
        next_state = self.fst.add_state()

        # Output tag substitution, if present
        if self.tag_substitution is not None:
            # Create ":WORD" that will always output at the end of the tag body
            output_idx = self.output_symbols.add_symbol(":" + self.tag_substitution)
            self.fst.add_arc(
                last_state,
                fst.Arc(self.in_eps, output_idx, self.weight_one, next_state),
            )

            last_state = next_state
            next_state = self.fst.add_state()

        # --[__end__TAG]-->
        end_symbol = "__end__" + self.tag_name
        output_idx = self.output_symbols.find(end_symbol)
        assert output_idx >= 0, f"{end_symbol} not found"

        self.fst.add_arc(
            last_state, fst.Arc(self.in_eps, output_idx, self.weight_one, next_state)
        )
        self.last_states[self.rule_name] = next_state

    # -------------------------------------------------------------------------
    # Literals
    # -------------------------------------------------------------------------

    def enterLiteral(self, ctx):
        if (not self.in_rule) or self.in_rule_reference:
            return

        super().enterLiteral(ctx)

        last_state = self.last_states[self.rule_name]

        # Split words by whitespace
        for in_word, out_word in self.literal_words:
            input_idx = self.input_symbols.find(in_word)
            output_idx = self.output_symbols.find(out_word)

            # --[word_in:word_out]-->
            next_state = self.fst.add_state()
            self.fst.add_arc(
                last_state, fst.Arc(input_idx, output_idx, self.weight_one, next_state)
            )
            self.exp_states[self.group_depth] = last_state
            last_state = next_state

        self.last_states[self.rule_name] = last_state
