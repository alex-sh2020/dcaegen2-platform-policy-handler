# ================================================================================
# Copyright (c) 2018-2020 AT&T Intellectual Property. All rights reserved.
# ================================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END=========================================================
#

"""utils and conversions"""

import json
import logging
import os
from copy import deepcopy
from typing import Pattern

class Utils(object):
    """general purpose utils"""
    _logger = logging.getLogger("policy_handler.utils")

    @staticmethod
    def get_logger(file_path):
        """get the logger for the file_path == __file__"""
        logger_path = []
        file_path = os.path.realpath(file_path)
        logger_path.append(os.path.basename(file_path)[:-3])
        while file_path:
            file_path = os.path.dirname(file_path)
            folder_name = os.path.basename(file_path)
            if folder_name == "policyhandler" or len(logger_path) > 5:
                break
            if folder_name == "tests":
                logger_path.append("unit_test")
                break
            logger_path.append(folder_name)

        logger_path.append("policy_handler")
        return logging.getLogger(".".join(reversed(logger_path)))

    @staticmethod
    def safe_json_parse(json_str):
        """try parsing json without exception - returns the json_str back if fails"""
        if not json_str:
            return json_str
        try:
            return json.loads(json_str)
        except (ValueError, TypeError) as err:
            Utils._logger.warning("unexpected json error(%s): len(%s) str[:100]: (%s)",
                                  str(err), len(json_str), str(json_str)[:100])
        return json_str

    @staticmethod
    def are_the_same(body_1, body_2, json_dumps=None):
        """check whether both objects are the same"""
        if not json_dumps:
            json_dumps = json.dumps
        if (body_1 and not body_2) or (not body_1 and body_2):
            Utils._logger.debug("only one is empty %s != %s", body_1, body_2)
            return False

        if body_1 is None and body_2 is None:
            return True

        if isinstance(body_1, list) and isinstance(body_2, list):
            if len(body_1) != len(body_2):
                Utils._logger.debug("len %s != %s", json_dumps(body_1), json_dumps(body_2))
                return False

            for val_1, val_2 in zip(body_1, body_2):
                if not Utils.are_the_same(val_1, val_2, json_dumps):
                    return False
            return True

        if isinstance(body_1, dict) and isinstance(body_2, dict):
            if body_1.keys() ^ body_2.keys():
                Utils._logger.debug("keys %s != %s", json_dumps(body_1), json_dumps(body_2))
                return False

            for key, val_1 in body_1.items():
                val_2 = body_2[key]
                if isinstance(val_1, str) or isinstance(val_2, str):
                    if val_1 != val_2:
                        Utils._logger.debug("key-values %s != %s",
                                            json_dumps({key: val_1}), json_dumps({key: val_2}))
                        return False
                    continue

                if not Utils.are_the_same(val_1, body_2[key], json_dumps):
                    return False
            return True

        # ... here when primitive values or mismatched types ...
        the_same_values = (body_1 == body_2)
        if not the_same_values:
            Utils._logger.debug("values %s != %s", body_1, body_2)
        return the_same_values

class RegexCoarser(object):
    """
    utility to combine or coarse the collection of regex patterns
    into a single regex that is at least not narrower (wider or the same)
    than the collection regexes

    inspired by https://github.com/spadgos/regex-combiner in js
    """
    ENDER = '***'
    GROUPERS = {'{': '}', '[': ']', '(': ')'}
    MODIFIERS = '*?+'
    CHOICE_STARTER = '('
    HIDDEN_CHOICE_STARTER = '(?:'
    ANY_CHARS = '.*'
    LINE_START = '^'

    def __init__(self, regex_patterns=None):
        """regex coarser"""
        self.trie = {}
        self.patterns = []
        self.add_regex_patterns(regex_patterns)

    def get_combined_regex_pattern(self):
        """gets the pattern for the combined regex"""
        trie = deepcopy(self.trie)
        RegexCoarser._compress(trie)
        return RegexCoarser._trie_to_pattern(trie)

    def get_coarse_regex_patterns(self, max_length=100):
        """gets the patterns for the coarse regex"""
        trie = deepcopy(self.trie)
        RegexCoarser._compress(trie)
        patterns = RegexCoarser._trie_to_pattern(trie, True)

        root_patterns = []
        for pattern in patterns:
            left, _, choice = pattern.partition(RegexCoarser.CHOICE_STARTER)
            if choice and left and left.strip() != RegexCoarser.LINE_START and not left.isspace():
                pattern = left + RegexCoarser.ANY_CHARS
            root_patterns.append(pattern)
        root_patterns = RegexCoarser._join_patterns(root_patterns, max_length)

        if not root_patterns or root_patterns == ['']:
            return []
        return root_patterns


    def add_regex_patterns(self, new_regex_patterns):
        """adds the new_regex patterns to RegexPatternCoarser"""
        if not new_regex_patterns or not isinstance(new_regex_patterns, list):
            return
        for new_regex_pattern in new_regex_patterns:
            self.add_regex_pattern(new_regex_pattern)

    def add_regex_pattern(self, new_regex_pattern):
        """adds the new_regex to RegexPatternCoarser"""
        new_regex_pattern = RegexCoarser._regex_pattern_to_string(new_regex_pattern)
        if not new_regex_pattern:
            return

        self.patterns.append(new_regex_pattern)

        tokens = RegexCoarser._tokenize(new_regex_pattern)
        last_token_idx = len(tokens) - 1
        trie_node = self.trie
        for idx, token in enumerate(tokens):
            if token not in trie_node:
                trie_node[token] = {}
            if idx == last_token_idx:
                trie_node[token][RegexCoarser.ENDER] = {}
            trie_node = trie_node[token]

    @staticmethod
    def _regex_pattern_to_string(regex_pattern):
        """convert regex pattern to string"""
        if not regex_pattern:
            return ''

        if isinstance(regex_pattern, str):
            return regex_pattern

        if isinstance(regex_pattern, Pattern):
            return regex_pattern.pattern
        return None

    @staticmethod
    def _tokenize(regex_pattern):
        """tokenize the regex pattern for trie assignment"""
        tokens = []
        token = ''
        group_ender = None
        use_next = False

        for char in regex_pattern:
            if use_next:
                use_next = False
                token += char
                char = None

            if char == '\\':
                use_next = True
                token += char
                continue

            if not group_ender and char in RegexCoarser.GROUPERS:
                group_ender = RegexCoarser.GROUPERS[char]
                token = char
                char = None

            if char is None:
                pass
            elif char == group_ender:
                token += char
                group_ender = None
                if char == '}': # this group is a modifier
                    tokens[len(tokens) - 1] += token
                    token = ''
                    continue
            elif char in RegexCoarser.MODIFIERS:
                if group_ender:
                    token += char
                else:
                    tokens[len(tokens) - 1] += char
                continue
            else:
                token += char

            if not group_ender:
                tokens.append(token)
                token = ''

        if token:
            tokens.append(token)
        return tokens

    @staticmethod
    def _compress(trie):
        """compress trie into shortest leaves"""
        for key, subtrie in trie.items():
            RegexCoarser._compress(subtrie)
            subkeys = list(subtrie.keys())
            if len(subkeys) == 1:
                trie[key + subkeys[0]] = subtrie[subkeys[0]]
                del trie[key]

    @staticmethod
    def _trie_to_pattern(trie, top_keep=False):
        """convert trie to the regex pattern"""
        patterns = [
            key.replace(RegexCoarser.ENDER, '') + RegexCoarser._trie_to_pattern(subtrie)
            for key, subtrie in trie.items()
        ]

        if top_keep:
            return patterns

        return RegexCoarser._join_patterns(patterns)[0]

    @staticmethod
    def _join_patterns(patterns, max_length=0):
        """convert list of patterns to the segmented list of dense regex patterns"""
        if not patterns:
            return ['']

        if len(patterns) == 1:
            return patterns

        if not max_length:
            return [RegexCoarser.HIDDEN_CHOICE_STARTER + '|'.join(patterns) + ')']

        long_patterns = []
        join_patterns = []
        for pattern in patterns:
            len_pattern = len(pattern)
            if not len_pattern:
                continue
            if len_pattern >= max_length:
                long_patterns.append(pattern)
                continue

            for idx, patterns_to_join in enumerate(join_patterns):
                patterns_to_join, len_patterns_to_join = patterns_to_join
                if len_pattern + len_patterns_to_join < max_length:
                    patterns_to_join.append(pattern)
                    len_patterns_to_join += len_pattern
                    join_patterns[idx] = (patterns_to_join, len_patterns_to_join)
                    len_pattern = 0
                    break
            if len_pattern:
                join_patterns.append(([pattern], len_pattern))
            join_patterns.sort(key=lambda x: x[1])

        if join_patterns:
            # pattern, _, choice = pattern.endswith(RegexCoarser.ANY_CHARS)
            join_patterns = [
                RegexCoarser.HIDDEN_CHOICE_STARTER + '|'.join(patterns_to_join) + ')'
                for patterns_to_join, _ in join_patterns
            ]

        return join_patterns + long_patterns
