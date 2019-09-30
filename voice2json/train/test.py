#!/usr/bin/env python3
import io
import tempfile
import unittest
from pathlib import Path

import networkx as nx

from ini_jsgf import make_grammars
from jsgf2fst import get_grammar_dependencies, grammar_to_fsts

from jsgf2fst.JsgfListener import JsgfListener

# -----------------------------------------------------------------------------


# class JsgfTestCase(unittest.TestCase):
#     def test_long_alternative(self):
#         """Generates a long alternative (1 | 2 | 3 | ...) to test the limits of the JSGF parser."""
#         n = 100
#         with tempfile.TemporaryDirectory() as temp_dir_str:
#             temp_dir = Path(temp_dir_str)
#             with io.StringIO() as ini_file:
#                 print("[TestIntent]", file=ini_file)
#                 print("(", "|".join(str(i) for i in range(100)), ")", file=ini_file)

#                 ini_file.seek(0)
#                 jsgf_path = make_grammars(ini_file, temp_dir)["TestIntent"]

#                 listener = grammar_to_fsts(jsgf_path.read_text())
#                 self.assertEqual("TestIntent", listener.grammar_name)
#                 self.assertIsNotNone(listener.fst)


class JsgfListenerTestCase(unittest.TestCase):
    def test_listener(self):
        """Basic tests of the JsgfListener."""
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            with io.StringIO() as ini_file:
                print("[TestIntent]", file=ini_file)
                print("test = [some]{the tag} rule", file=ini_file)
                print("<test>", file=ini_file)

                ini_file.seek(0)
                jsgf_path = make_grammars(ini_file, temp_dir)["TestIntent"]

                grammar_text = jsgf_path.read_text().strip()
                # print(grammar_text)
                listener = JsgfTestListener(grammar_text)
                listener.walk()

                self.assertEqual("TestIntent", listener.grammar_name)
                self.assertIn((True, "TestIntent"), listener.rules)
                self.assertIn((False, "test"), listener.rules)
                self.assertGreater(listener.group_count, 0)
                self.assertEqual("the tag", listener.tag_name)


# -----------------------------------------------------------------------------


class JsgfTestListener(JsgfListener):
    def __init__(self, grammar):
        JsgfListener.__init__(self, grammar)
        self.group_count = 0
        self.rules = []
        self.in_alternative = False
        self.alt_literals = []
        self.tag_name = None

    def enterGrammarName(self, ctx):
        self.grammar_name = ctx.getText()

    def enterRuleName(self, ctx):
        self.rules.append((ctx.PUBLIC(), ctx.getText()))

    def enterTagBody(self, ctx):
        self.tag_name = ctx.getText()

    def enterAlternative(self, ctx):
        self.in_alternative = True

    def exitAlternative(self, ctx):
        self.in_alternative = False

    def enterGroup(self, ctx):
        self.group_count += 1

    def enterLiteral(self, ctx):
        if self.in_alternative:
            self.alt_literals.append(ctx.getText())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
