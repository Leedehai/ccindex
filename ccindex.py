#!/usr/bin/env python
# Author: Haihong L.
# License: MIT License
#
# DESCRIPTION:
# This is a script that extracts symbols defined in C++, along with each
# symbol's meta information: syntax kind, type, location, documentation, etc.
# The extracted information could be used to generate API documenation.
#
# REQUIRED:
# libclang, normally came with a Clang installation
# Python module 'clang', install: pip install clang)
#
# USAGE:
# 1) as a commandline tool, print to stdout:
#        ./ccindex.py path/file.[h|cc]
#        ./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2
# 2) as a commandline tool, store as JSON:
#        ./ccindex.py path/file.[h|cc]
#        ./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -json
# 3) as a commandline tool, store as sqlite database:
#        ./ccindex.py path/file.[h|cc]
#        ./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -db
# 4) as Python library (import ccindex):
#        result = ccindex.get("path/file.h", ["UserIncludeDir1", "UserIncludeDir2"])
#        the return is a dict
# NOTE if the source file includes headers, header directories must be specified
#      with the "-i" option, otherwise some symbols won't be recognized.
#
# LIMITATION:
# only on macOS; for Linux, modify LIBCLANG_PATH_CANDIDATES and SYS_INCLUDE_PATHS

import sys, os, time
import re
import argparse
try:
    import clang.cindex as cindex # pip install clang
except:
    print("[Error] module 'cindex' required, install: pip install clang")
    sys.exit(1)

"""
User configs
"""

# for libclang.dylib -- required
LIBCLANG_PATH_CANDIDATES = [
    "/Library/Developer/CommandLineTools/usr/lib"
    # or your locally-compiled libclang path
]
# system root path
SYSROOT_PATH = "/" # or on macOS "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"
# system include paths
SYS_INCLUDE_PATHS = [
    # only valid on macOS
    "/Library/Developer/CommandLineTools/usr/include/c++/v1",
    "/usr/include"
]

found_candidate = False
for candidate in LIBCLANG_PATH_CANDIDATES:
    if os.path.isdir(candidate):
        found_candidate = True
        cindex.Config.set_library_path(candidate)
if not found_candidate:
    print("[Error] library path of libclang not found")
    sys.exit(1)

interested_CursorKinds = [
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
    cindex.CursorKind.CXX_METHOD,
    cindex.CursorKind.CONVERSION_FUNCTION,
    cindex.CursorKind.FUNCTION_TEMPLATE,
    cindex.CursorKind.CLASS_TEMPLATE,
    cindex.CursorKind.ENUM_DECL,
    cindex.CursorKind.ENUM_CONSTANT_DECL,
    cindex.CursorKind.FIELD_DECL,
    cindex.CursorKind.CLASS_DECL,
    cindex.CursorKind.STRUCT_DECL,
    cindex.CursorKind.FUNCTION_DECL,
    cindex.CursorKind.VAR_DECL,
    cindex.CursorKind.TYPEDEF_DECL,
    # ...
]

"""
Formatting
"""

def _format_comment(raw_comment):
    if raw_comment == None:
        return "", ""
    comment_lines = []
    inside_usage_block = False
    usage_lines = []
    for line in raw_comment.split("\n"):
        line = re.sub(r"\A\/\*\*", "", line)
        line = re.sub(r"\A\/\*\< ", "", line)
        line = re.sub(r"\A\s*\* ", "", line)
        line = re.sub(r"\*\/", "", line)
        comment_lines.append(line)
        if line.strip().startswith("Usage:"):
            inside_usage_block = True
        if line.strip().startswith("-----"):
            inside_usage_block = False
        if inside_usage_block:
            usage_lines.append(line.replace("Usage:", "").lstrip())
    entire_content = '\n'.join(comment_lines).strip()
    return entire_content, "\n".join(usage_lines)

def _format_location(location):
    return "%s:%s:%s" % (str(location.file), int(location.line), int(location.column))

def _is_transparent_decl(cursor):
    return (cursor.kind == cindex.CursorKind.ENUM_DECL) and (not cursor.is_scoped_enum())

def _format_sematic_parent(cursor):
    if cursor.semantic_parent.kind == cindex.CursorKind.TRANSLATION_UNIT:
        return "", "(global)"
    # return tuple element #0
    hierarchy_list = [] # top first, each level's spelling
    transparency_list = [] # top first, each level's transparency (e.g. non-scoped enum is transparent)
    temp_cursor = cursor
    while True: # from child to parent, all the way up to the translation unit node
        temp_cursor = temp_cursor.semantic_parent
        if temp_cursor.kind == cindex.CursorKind.TRANSLATION_UNIT:
            break
        temp_cursor_spelling = temp_cursor.spelling
        if not temp_cursor_spelling:
            # anonymous, e.g. "typedef struct { ... } MyType_t;", then we use the type alias "MyType_t"
            temp_cursor_spelling = temp_cursor.type.spelling.split("::")[-1]
        # insert to front, because we are going from buttom-up
        hierarchy_list.insert(0, temp_cursor_spelling)
        transparency_list.insert(0, True if _is_transparent_decl(temp_cursor) else False)
    # return tuple element #1
    parent_kind_str = str(cursor.semantic_parent.kind).split(".")[-1]
    parent_kind_str = "%s" % parent_kind_str.replace("_DECL", "").replace("_", " ").lower()
    return zip(hierarchy_list, transparency_list), parent_kind_str

def _format_syntax_kind(kind):
    kind_str = str(kind).split(".")[-1]
    kind_str = kind_str.replace("CXX_", "").replace("_DECL", "").replace(" ", "").replace("VAR", "VARIABLE")
    return kind_str.lower()

def _format_type(type_obj):
    type_str = type_obj.spelling
    type_str = type_str.replace("std::__1::", "std::")
    type_str = re.sub(r" *\*", "*", type_str)
    type_str = re.sub(r" *&", "&", type_str)
    return type_str

no_return_funcs_CursorKindCursorKind = [ # no return type
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
]
def _format_func_proto(cursor): # ordinary function/method templated function/method
    # go through child elements, collecting ordinary args and possibly template params
    template_params_list = []
    args_list = []
    for c in cursor.get_children():
        if c.kind == cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
            template_params_list.append(("typename", c.spelling))
        elif c.kind == cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            template_params_list.append((_format_type(c.type), c.spelling))
        elif c.kind == cindex.CursorKind.PARM_DECL: # the args in the parenthesis
            if len(str(c.spelling)):
                args_list.append((_format_type(c.type), c.spelling))
            else: # unamed argument in prototype declaration
                args_list.append((_format_type(c.type), ""))
    # 1. possibly function template header
    template_header = ""
    if template_params_list:
        template_header = "template <%s>" % ", ".join(["%s %s" % item for item in template_params_list])
    # 2. return type
    if cursor.kind in no_return_funcs_CursorKindCursorKind:
        return_type = None
    else:
        return_type = _format_type(cursor.result_type)
    # 3. function name
    func_name = str(cursor.displayname).split('(')[0]
    # 4. const qualifier
    const_qualifier = "const" if cursor.is_const_method() else ""
    # build prototype string (without template header)
    args_repr_list = [ ("%s %s" % item).strip() for item in args_list] # join type and arg name (may be absent)
    if return_type and cursor.kind != cindex.CursorKind.CONVERSION_FUNCTION:
        return_type_func_name = "%s %s" % (return_type, func_name)
    else:
        return_type_func_name = func_name
    proto_str = "%s(%s) %s" % (return_type_func_name, ', '.join(args_repr_list), const_qualifier)
    proto_str_pretty = proto_str
    if len(proto_str) > 75:
        proto_str_pretty = "%s(\n%s\n) %s" % (return_type_func_name,
                                              ",\n".join(["\t%s" % arg for arg in args_repr_list]),
                                              const_qualifier)
    proto_str = proto_str if not template_header else template_header + "\n" + proto_str
    return (proto_str.strip(), proto_str_pretty.strip()), template_params_list, args_list, return_type

def _format_class_proto(cursor):
    template_params_list = []
    for c in cursor.get_children():
        if c.kind == cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
            template_params_list.append(("typename", c.spelling))
        elif c.kind == cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            template_params_list.append((_format_type(c.type), c.spelling))
    template_header = ""
    if template_params_list:
        template_header = "template <%s>" % ", ".join(["%s %s" % item for item in template_params_list])
    class_name_str = "class %s" % cursor.spelling
    class_name_str = class_name_str if not template_header else "%s %s" % (template_header, class_name_str)
    class_name_str_pretty = class_name_str if not template_header else "%s\n%s" % (template_header, class_name_str)
    return (class_name_str.strip(), class_name_str_pretty.strip()), template_params_list

"""
Index visiting
"""
func_like_CursorKind = [ # function-like
    cindex.CursorKind.FUNCTION_DECL,
    cindex.CursorKind.FUNCTION_TEMPLATE,
    cindex.CursorKind.CONVERSION_FUNCTION,
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
    cindex.CursorKind.CXX_METHOD
]

class_like_CursorKind = [ # class-like
    cindex.CursorKind.CLASS_DECL,
    cindex.CursorKind.STRUCT_DECL,
    cindex.CursorKind.CLASS_TEMPLATE
]

val_like_CursorKind = [ # value-like
    cindex.CursorKind.VAR_DECL,
    cindex.CursorKind.FIELD_DECL,
    cindex.CursorKind.ENUM_CONSTANT_DECL
]

def _visit_cursor(c): # visit an AST node (pointed by cursor), returning a symbol dict
    symbol = {} # dict for this symbol
    # part 1. mandated fields
    symbol["spelling"] = "%s" % c.spelling # str
    hierarchy_and_kind = _format_sematic_parent(c) # tuple
    symbol["hierarchy"] = hierarchy_and_kind[0] # list of tuple (spelling, transparency), might be empty, starting from top-level
    symbol["parent_kind"] = hierarchy_and_kind[1] # str
    symbol["location"] = _format_location(c.location) # str
    symbol["kind"] = _format_syntax_kind(c.kind) # str
    comment_tuple = _format_comment(c.raw_comment)
    symbol["comment"] = comment_tuple[0] # str
    symbol["usage"] = comment_tuple[1] # str
    # part 2. optional fields
    if c.kind in func_like_CursorKind:
        func_proto_tuple = _format_func_proto(c)
        symbol["declaration"] = "%s;" % func_proto_tuple[0][0] # str
        symbol["declaration_pretty"] = "%s;" % func_proto_tuple[0][1] # str
        symbol["is_template"] = True if func_proto_tuple[1] else False# boolean
        symbol["template_args_list"] = func_proto_tuple[1] # list of tuple (type, arg name)
        symbol["args_list"] = func_proto_tuple[2] # # list of tuple (type, arg name)
        symbol["return_type"] = func_proto_tuple[3] # str or NoneType (e.g. constructor's return type is None)
    elif c.kind in class_like_CursorKind:
        class_proto_tuple = _format_class_proto(c)
        symbol["declaration"] = "%s;" % class_proto_tuple[0][0] # str
        symbol["declaration_pretty"] = "%s;" % class_proto_tuple[0][1] # str
        symbol["is_template"] = True if class_proto_tuple[1] else False# boolean
        symbol["template_args_list"] = class_proto_tuple[1] # list of tuple (type, arg name)
    if c.semantic_parent.kind in class_like_CursorKind:
        symbol["access"] = str(c.access_specifier).split('.')[-1].lower() # str
    if c.kind in val_like_CursorKind + [ cindex.CursorKind.CLASS_DECL, cindex.CursorKind.STRUCT_DECL ]:
        sizeof_type = c.type.get_size()
        symbol["size"] = sizeof_type if sizeof_type > 0 else None # int or NoneType
        symbol["POD"] = c.type.is_pod() # boolean (POD: Plain Old Data)
        if c.type.kind == cindex.TypeKind.TYPEDEF:
            symbol["type"] = (
                _format_type(c.type), {
                    "typedef": True,
                    "typename": False,
                    "canonical_type": _format_type(c.type.get_canonical()) # real type, completely resoluted
                }
             ) # tuple of (str, dict)
        elif c.type.kind == cindex.TypeKind.UNEXPOSED:
            symbol["type"] = ( _format_type(c.type), { "typedef": False, "typename": True } ) # tuple of (str, dict)
        else:
            symbol["type"] = ( _format_type(c.type), { "typedef": False, "typename": False } ) # tuple of (str, dict)
    if c.kind == cindex.CursorKind.TYPEDEF_DECL:
        symbol["typedef_underlying"] = _format_type(c.underlying_typedef_type) # str
    if c.kind == cindex.CursorKind.CONSTRUCTOR:
        if c.is_default_constructor():
            symbol["constructor_kind"] = "default" # str
        elif c.is_copy_constructor():
            symbol["constructor_kind"] = "copy" # str
        elif c.is_move_constructor():
            symbol["constructor_kind"] = "move" # str
        elif c.is_converting_constructor():
            symbol["constructor_kind"] = "converting" # str
    if (c.semantic_parent.kind in class_like_CursorKind
        and c.kind == cindex.CursorKind.VAR_DECL):
        # static member is of VAR_DECL kind instead of FIELD_DECL kind
        symbol["static_member"] = True # boolean
    if c.kind == cindex.CursorKind.FIELD_DECL:
        symbol["static_member"] = False # boolean
    if c.kind == cindex.CursorKind.CXX_METHOD:
        method_kind = []
        if c.is_static_method():
            method_kind.append("static")
        if c.is_const_method():
            method_kind.append("const")
        if c.is_default_method(): # marked by "= default"
            method_kind.append("default")
        if c.is_virtual_method():
            method_kind.append("virtual")
        if c.is_pure_virtual_method():
            method_kind.append("pure virtual")
        symbol["method_kind"] = method_kind # list
    if c.kind == cindex.CursorKind.ENUM_DECL:
        symbol["scoped_enum"] = True if c.is_scoped_enum() else False
        symbol["enum_type"] = c.enum_type.spelling
    if c.kind == cindex.CursorKind.ENUM_CONSTANT_DECL:
        symbol["enum_type"] = c.type.get_declaration().enum_type.spelling
        symbol["enum_value"] = c.enum_value
    return symbol

def _traverse_ast(root_node, target_filename, print_out):
    symbols = [] # list of symbol dicts
    for c in root_node.walk_preorder():
        if str(c.location.file) != target_filename:
            continue # skip header files
        if c.kind not in interested_CursorKinds:
            continue # skip uninterested node
        if not c.spelling:
            continue # skip anonymous node, e.g. anonymous struct declaration
        # visit this node entity, get a dict
        symbol = _visit_cursor(c)
        # collect to symbols list
        symbols.append(symbol)
        # print to stdout
        if symbol and print_out:
            _print_to_stdout(symbol)
    return symbols # [ symbol_dict_1, symbol_dict_2 ]

"""
Input/Output
"""

ordered_keys = ["spelling", "kind", "hierarchy", "parent_kind", "location", "comment", "usage"]
def _print_to_stdout(symbol):
    # print keys in ordered_keys first, in order; they are present in all symbol dicts
    for key in ordered_keys:
        if key == "hierarchy":
            if not symbol[key]:
                print("hierarchy:\n\t(none)")
            else:
                hierarchy_repr_list = []
                for i in range(len(symbol[key])):
                    spelling, transparent = symbol[key][i][0], symbol[key][i][1]
                    hierarchy_repr_list.append(spelling if not transparent else ("(%s)" % spelling))
                print("hierarchy:\n\t%s" % ("::" + "::".join(hierarchy_repr_list)))
        elif key == "comment":
            comment = symbol[key]
            print("comment:\n```\n%s\n```" % (comment if comment else "(none)"))
        elif key == "usage":
            usage = symbol[key]
            if usage:
                print("usage:\n```\n%s\n```" % usage)
        else:
            print("%s:\n\t%s" % (key, symbol[key]))
    # print other keys
    for key, value in symbol.items():
        if key not in ordered_keys:
            print("%s:\n\t%s" % (key, str(value)))
    print("-----")

def _verify_include_paths(include_paths, user_include_paths):
    path_not_found = []
    for path in include_paths:
        if not os.path.isdir(path):
            path_not_found.append(path)
    if len(path_not_found):
        print("[Error] include path%s not found:" % ("s" if len(path_not_found) > 1 else ""))
        for path in path_not_found:
            print("\t%s%s" % (path, " (user provided)" if path in user_include_paths else "(system)"))
        return False
    return True

def _get_symbols(target_filename, user_include_paths_str, as_library, to_database, to_json):
    include_paths = SYS_INCLUDE_PATHS
    user_include_paths = []
    # user include paths
    if user_include_paths_str: # not empty string
        user_include_paths = [item.strip() for item in user_include_paths_str.split(',')]
        include_paths += user_include_paths
    if not _verify_include_paths(include_paths, user_include_paths):
        sys.exit(1)

    # check printing
    print_out = (not as_library) and (not to_json) and (not to_database)

    # build index of source
    start_time = time.time()
    index = cindex.Index.create()
    indexing_time = time.time() - start_time

    clang_args = "-x c++ --std=c++14".split()
    clang_args += ("-isysroot %s" % SYSROOT_PATH).split()
    clang_args += [ "-I" + path for path in include_paths ]

    tu = index.parse(target_filename, args=clang_args, options=cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES)
    if print_out:
        print("[TARGET FILE] %s" % tu.spelling)
    start_time = time.time()
    # symbols: [ symbol_dict_1, symbol_dict_2 ]
    symbols = _traverse_ast(tu.cursor, target_filename, print_out)
    traversing_time = time.time() - start_time

    # for any error, it is programmer's responsibility to inspect tu.diagnostics
    # NOTE especially, if a type is unrecognized (e.g. caused by not including the corresponding header),
    #      the displayed type spelling will be "int"
    errors = [] # list error strings
    error_count = 0
    for diagnostic in tu.diagnostics:
        error_count += 1
        errors.append(str(diagnostic))
        if print_out:
            print("[Diagnostic #%d]\n%s" % (error_count, errors[error_count - 1]))
    if print_out:
        print("[indexing time] %.2f sec" % indexing_time)
        print("[traverse time] %.2f sec" % traversing_time)
    # build result
    result = {
        "symbols": symbols, # list of symbol dicts
        "errors": errors,   # list of error strings
        "indexing_time": indexing_time,    # float, in seconds
        "traversing_time": traversing_time # float, in seconds
    }
    if to_json:
        import json
        with open(to_json, 'w') as json_file: # overwrite if exists
            json.dump(result, json_file, indent=2)
    return result

# exposed as library interface, returning a dict
def get(target_filename, user_include_path_list=[]):
    result = _get_symbols(target_filename=args.filename,
                          user_include_paths_str=','.join(user_include_path_list),
                          as_library=True, to_database=None, to_json=None)
    return result

"""
Commandline utility interface
"""

def get_arg_parser():
    arg_parser = argparse.ArgumentParser(description="Generate summary of symbols in a C++ source file",
                                         epilog="if neither -json nor -db is given, then write result to stdout")
    arg_parser.add_argument("filename", nargs=1, type=str, default="",
                            help="path to file to be parsed")
    arg_parser.add_argument("-i", "--user-include-paths", type=str, default="",
                        help="comma separated list of user include paths, e.g. dir1/dir2,dir3/dir4")
    arg_parser.add_argument("-json", "--to-json", nargs='?', type=str, const="out.json", default=None,
                        help="write to json file (default: out.json)")
    arg_parser.add_argument("-db", "--to-database", nargs='?', type=str, const="out.db", default=None,
                        help="write to a sqlite database file (default: out.db)")
    return arg_parser

if __name__ == "__main__":
    args = get_arg_parser().parse_args()

    if len(args.filename) == 0:
        print("[Error] source file not given")
        sys.exit(1)
    args.filename = args.filename[0]
    if not os.path.isfile(args.filename):
        print("[Error] source file not found: %s" % args.filename)
        sys.exit(1)

    _get_symbols(target_filename=args.filename,
                 user_include_paths_str=args.user_include_paths,
                 as_library=False,
                 to_database=args.to_database,
                 to_json=args.to_json)