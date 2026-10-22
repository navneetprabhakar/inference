"""Finite literal temporal qualifier adapter; no source application or expansion engine."""
import hashlib
import re


class Hold(ValueError):
    pass


def literal_year_qualifier(node):
    """Return a reversible-operation proposal for a single literal year only.

    The caller must bind this complete AST node to its original source span.
    Other template names, options, date forms and nested expressions remain held.
    """
    if type(node).__name__ != 'Template':
        raise Hold('not_a_template')
    if any(type(part).__name__ != 'Text' for part in node.name.nodes):
        raise Hold('nonliteral_template_name')
    if str(node.name).strip() not in ('As of', 'as of'):
        raise Hold('unsupported_template_name')
    if len(node.params) != 1:
        raise Hold('only_one_literal_year_parameter_supported')
    parameter = node.params[0]
    if any(type(part).__name__ != 'Text' for part in parameter.name.nodes):
        raise Hold('nonliteral_parameter_name')
    if str(parameter.name).strip() != '1':
        raise Hold('unsupported_parameter_name')
    if any(type(part).__name__ != 'Text' for part in parameter.value.nodes):
        raise Hold('nonliteral_year_value')
    year = str(parameter.value).strip()
    if re.fullmatch(r'[1-9][0-9]{3}', year) is None:
        raise Hold('unsupported_year_format')
    raw = str(node)
    return {
        'kind': 'literal_year_temporal_qualifier',
        'raw': raw,
        'raw_SHA256': hashlib.sha256(raw.encode('utf8')).hexdigest(),
        'replacement': 'As of ' + year,
        'year_literal': year,
        'temporal_scope_preserved': True,
        'source_span_binding_required': True,
        'factual_verification_or_template_engine_equivalence': False,
        'new_admitted_documents': 0,
    }
