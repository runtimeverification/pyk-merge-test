from __future__ import annotations

from typing import TYPE_CHECKING

from .kast.inner import KApply, KRewrite, KSequence
from .kast.outer import KRule, read_kast_definition

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

    from .kast.outer import KDefinition


def get_rule_by_id(definition: KDefinition, rule_id: str) -> KRule:
    """Get a rule from the definition by coverage rule id.

    Input:

        -   definition: json encoded definition.
        -   rule_id: string of unique rule identifier generated by `kompile --coverage`.

    Output: json encoded rule which has identifier rule_id.
    """

    for module in definition.modules:
        for sentence in module.sentences:
            if type(sentence) is KRule:
                if 'UNIQUE_ID' in sentence.att and sentence.att['UNIQUE_ID'] == rule_id:
                    return sentence
    raise ValueError(f'Could not find rule with ID: {rule_id}')


def strip_coverage_logger(rule: KRule) -> KRule:
    body = rule.body
    if type(body) is KRewrite:
        lhs = body.lhs
        rhs = body.rhs
        if type(rhs) is KApply and rhs.label.name.startswith('project:'):
            rhs_seq = rhs.args[0]
            if type(rhs_seq) is KSequence and rhs_seq.arity == 2:
                body = KRewrite(lhs, rhs_seq.items[1])
    return rule.let(body=body)


def translate_coverage(
    src_all_rules: Iterable[str],
    dst_all_rules: Iterable[str],
    dst_definition: KDefinition,
    src_rules_list: Iterable[str],
) -> list[str]:
    """Translate the coverage data from one kompiled definition to another.

    Input:

        -   src_all_rules: contents of allRules.txt for definition which coverage was generated for.
        -   dst_all_rules: contents of allRules.txt for definition which you desire coverage for.
        -   dst_definition: JSON encoded definition of dst kompiled definition.
        -   src_rules_list: Actual coverage data produced.

    Output: list of non-functional rules applied in dst definition translated from src definition.
    """

    # Load the src_rule_id -> src_source_location rule map from the src kompiled directory
    src_rule_map = {}
    for line in src_all_rules:
        src_rule_hash, src_rule_loc = line.split(' ')
        src_rule_loc = src_rule_loc.split('/')[-1]
        src_rule_map[src_rule_hash.strip()] = src_rule_loc.strip()

    # Load the dst_rule_id -> dst_source_location rule map (and inverts it) from the dst kompiled directory
    dst_rule_map = {}
    for line in dst_all_rules:
        dst_rule_hash, dst_rule_loc = line.split(' ')
        dst_rule_loc = dst_rule_loc.split('/')[-1]
        dst_rule_map[dst_rule_loc.strip()] = dst_rule_hash.strip()

    src_rule_list = [rule_hash.strip() for rule_hash in src_rules_list]

    # Filter out non-functional rules from rule map (determining if they are functional via the top symbol in the rule being `<generatedTop>`)
    dst_non_function_rules = []
    for module in dst_definition.modules:
        for sentence in module.sentences:
            if type(sentence) is KRule:
                body = sentence.body
                if (type(body) is KApply and body.label.name == '<generatedTop>') or (
                    type(body) is KRewrite and type(body.lhs) is KApply and body.lhs.label.name == '<generatedTop>'
                ):
                    if 'UNIQUE_ID' in sentence.att:
                        dst_non_function_rules.append(sentence.att['UNIQUE_ID'])

    # Convert the src_coverage rules to dst_no_coverage rules via the maps generated above
    dst_rule_list = []
    for src_rule in src_rule_list:
        if src_rule not in src_rule_map:
            raise ValueError(f'Could not find rule in src_rule_map: {src_rule}')
        src_rule_loc = src_rule_map[src_rule]

        if src_rule_loc not in dst_rule_map:
            raise ValueError(f'Could not find rule location in dst_rule_map: {src_rule_loc}')
        dst_rule = dst_rule_map[src_rule_loc]

        if dst_rule in dst_non_function_rules:
            dst_rule_list.append(dst_rule)

    return dst_rule_list


def translate_coverage_from_paths(src_kompiled_dir: str, dst_kompiled_dir: str, src_rules_file: PathLike) -> list[str]:
    """Translate coverage information given paths to needed files.

    Input:

        -   src_kompiled_dir: Path to *-kompiled directory of source.
        -   dst_kompiled_dir: Path to *-kompiled directory of destination.
        -   src_rules_file: Path to generated rules coverage file.

    Output: Translated list of rules with non-semantic rules stripped out.
    """
    src_all_rules = []
    with open(src_kompiled_dir + '/allRules.txt') as src_all_rules_file:
        src_all_rules = [line.strip() for line in src_all_rules_file]

    dst_all_rules = []
    with open(dst_kompiled_dir + '/allRules.txt') as dst_all_rules_file:
        dst_all_rules = [line.strip() for line in dst_all_rules_file]

    dst_definition = read_kast_definition(dst_kompiled_dir + '/compiled.json')

    src_rules_list = []
    with open(src_rules_file) as src_rules:
        src_rules_list = [line.strip() for line in src_rules]

    return translate_coverage(src_all_rules, dst_all_rules, dst_definition, src_rules_list)
