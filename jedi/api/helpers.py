"""
Helpers for the API
"""
import re

from jedi.parser import tree as pt
from jedi.evaluate import imports
from jedi.evaluate import compiled


def completion_parts(path_until_cursor):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path_until_cursor, flags=re.S)
    return match.groups()


def sorted_definitions(defs):
    # Note: `or ''` below is required because `module_path` could be
    return sorted(defs, key=lambda x: (x.module_path or '', x.line or 0, x.column or 0))


def name_like(name, like, case_insensitive):
    if case_insensitive:
        name = name.lower()
        like = like.lower()
    return name.startswith(like)


def get_named_params(call_signatures):
    named_params = []
    # add named params
    for call_sig in call_signatures:
        # Allow protected access, because it's a public API.
        module = call_sig._name.get_parent_until()
        # Compiled modules typically don't allow keyword arguments.
        if not isinstance(module, compiled.CompiledObject):
            for p in call_sig.params:
                # Allow access on _definition here, because it's a
                # public API and we don't want to make the internal
                # Name object public.
                if p._definition.stars == 0:  # no *args/**kwargs
                    named_params.append(p._name)
    return named_params


def get_on_import_stmt(evaluator, user_context, user_stmt, is_like_search=False):
    """
    Resolve the user statement, if it is an import. Only resolve the
    parts until the user position.
    """
    name = user_stmt.name_for_position(user_context.position)
    if name is None:
        return None, None

    i = imports.ImportWrapper(evaluator, name)
    return i, name


def check_error_statements(module, pos):
    for error_stmt in module.error_statement_stacks:

        import_error = error_stmt.first_type in ('import_from', 'import_name')
        error_on_pos = error_stmt.first_pos < pos <= error_stmt.next_start_pos

        if import_error and error_on_pos:
            return importer_from_error_statement(error_stmt, pos)
    return None, 0, False, False


def importer_from_error_statement(error_statement, pos):
    def check_dotted(children):
        for name in children[::2]:
            if name.start_pos <= pos:
                yield name

    names = []
    level = 0
    only_modules = True
    unfinished_dotted = False
    for typ, nodes in error_statement.stack:
        if typ == 'dotted_name':
            names += check_dotted(nodes)
            if nodes[-1] == '.':
                # An unfinished dotted_name
                unfinished_dotted = True
        elif typ == 'import_name':
            if nodes[0].start_pos <= pos <= nodes[0].end_pos:
                # We are on the import.
                return None, 0, False, False
        elif typ == 'import_from':
            for node in nodes:
                if node.start_pos >= pos:
                    break
                elif isinstance(node, pt.Node) and node.type == 'dotted_name':
                    names += check_dotted(node.children)
                elif node in ('.', '...'):
                    level += len(node.value)
                elif isinstance(node, pt.Name):
                    names.append(node)
                elif node == 'import':
                    only_modules = False

    return names, level, only_modules, unfinished_dotted
