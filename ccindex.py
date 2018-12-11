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
#        ./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -json out.json
# 3) as a commandline tool, store as SQLite database:
#        ./ccindex.py path/file.[h|cc]
#        ./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -db out.db
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
    cindex.CursorKind.NAMESPACE,
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
    cindex.CursorKind.TYPE_ALIAS_DECL,
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
    if not location.file:
        return "" # e.g. the location of built-in "float" type
    return "%s:%s:%s" % (str(location.file), int(location.line), int(location.column))

def _is_transparent_decl(cursor):
    return (cursor.kind == cindex.CursorKind.ENUM_DECL) and (not cursor.is_scoped_enum())

def _format_hierarchy(cursor):
    if cursor.semantic_parent.kind == cindex.CursorKind.TRANSLATION_UNIT:
        return [], "(global)"
    # return tuple element #0
    # top-level first
    spelling_list = []     # each level's spelling
    transparency_list = [] # each level's transparency (e.g. non-scoped enum is transparent)
    syntax_kind_list = []  # each level's syntax kind (e.g. namespace, class, enum)
    location_list = []     # each level's source location string
    temp_cursor = cursor
    while True: # from child to parent, all the way up to the translation unit node
        temp_cursor = temp_cursor.semantic_parent
        if temp_cursor.kind == cindex.CursorKind.TRANSLATION_UNIT:
            break
        temp_cursor_spelling = temp_cursor.spelling
        if not temp_cursor_spelling:
            # anonymous, e.g. "typedef struct { ... } MyType_t;", then we use the type alias "MyType_t"
            temp_cursor_spelling = temp_cursor.type.spelling.split("::")[-1]
        # insert to front, because we are going buttom-up
        spelling_list.insert(0, temp_cursor_spelling)
        transparency_list.insert(0, True if _is_transparent_decl(temp_cursor) else False)
        syntax_kind_list.insert(0, _format_syntax_kind(temp_cursor.kind))
        location_list.insert(0, _format_location(temp_cursor.location))
    # return tuple element #1
    parent_kind_str = syntax_kind_list[-1] # the intermediate parent
    # build return list
    hierarchy_dict_list = [ {
        "spelling": spelling_list[i],
        "transparent": transparency_list[i],
        "kind": syntax_kind_list[i],
        "location": location_list[i]
    } for i in range(len(spelling_list)) ]
    return hierarchy_dict_list, parent_kind_str

def _format_syntax_kind(kind):
    kind_str = str(kind).split(".")[-1].lower().replace("cxx_", "")
    kind_str = kind_str.replace("_decl", "_declaration").replace("var_", "variable_")
    return kind_str

def _find_hierarchy_item_for_owning_template(hierarchy, template_level):
    template_hierarchy_list = [ item for item in hierarchy if ("template" in item["kind"]) ]
    if template_level >= len(template_hierarchy_list):
        return None # unexpected
    return template_hierarchy_list[template_level] # dict
def _format_type_param_decl_location(type_obj, hierarchy):
    # the canonical type of a template type param is "type-parameter-X-Y",
    # where X is the level of nested template (the outmost is 0), and Y
    # is the position of this param (starts with 0) in that level's template
    # declaration. Example:
    # template <typename T> class A {                      // level 0
    #     class Class B {                                  // not a template declaration
    #         template <unsigned N, typename U> class C {  // level 1
    #             using UU = U;
    #             // type alias UU's canonical type spelling is "type-parameter-1-1"
    #         };
    #     };
    # };
    canonical_spelling = type_obj.get_canonical().spelling # "type-parameter-X-Y"
    assert canonical_spelling.startswith("type-parameter-")
    owning_template_level, template_param_pos = tuple(int(n) for n in canonical_spelling.split("-")[-2:])
    owning_template = _find_hierarchy_item_for_owning_template(hierarchy, owning_template_level)
    return {
        "location": owning_template["location"] if owning_template else "",
        "spelling": owning_template["spelling"] if owning_template else "(not found)",
        "index":    template_param_pos if owning_template else -1,
    }

def _format_type_spelling(type_str):
    type_str = type_str.replace("std::__1::", "std::")
    type_str = re.sub(r" *\*", "*", type_str)     # e.g. "int *" => "int*"
    type_str = re.sub(r" *&", "&", type_str)      # e.g. "int &" => "int&"
    type_str = re.sub(r"\> *\>", ">>", type_str)  # e.g. "C1<C2<int> >" => "C1<C2<int>>"
    type_str = type_str.replace(" [", "[")        # e.g. "int [5]" => "int[5]"
    return type_str

def _format_type(type_obj):
    type_str = type_obj.spelling
    if type_str.startswith("type-parameter-"):
        return "(type parameter)"
    return _format_type_spelling(type_str)

def _get_type_alias_chain(type_obj):
    chain = [ type_obj ] # list of cindex.Type object
    temp_type = type_obj
    while True:
        if temp_type.get_declaration().kind == cindex.CursorKind.NO_DECL_FOUND:
            break
        temp_type = temp_type.get_declaration().underlying_typedef_type
        if temp_type.spelling and chain[-1].spelling != temp_type.spelling:
            chain.append(temp_type)
        else:
            break
    return chain # this type obj first, completely resoluted last
def _format_type_alias_chain(type_obj):
    chain = _get_type_alias_chain(type_obj)
    return [ {
        "spelling": item.spelling,
        "location": _format_location(item.get_declaration().location)
    } for item in chain ]

no_return_funcs_CursorKindCursorKind = [ # no return type
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
]
noexcept_ExceptionSpecificationKind = [
    cindex.ExceptionSpecificationKind.DYNAMIC_NONE,   # throw(), deprecated since C++11, supported for legacy
    cindex.ExceptionSpecificationKind.BASIC_NOEXCEPT, # noexcept
]
def _format_func_proto(cursor): # ordinary function/method templated function/method
    # go through child elements, collecting ordinary args and possibly template params
    template_params_list = []
    args_list = []
    # specifiers
    is_final = False
    is_override = False
    is_pure_virtual = False
    is_no_throw_bool_or_None = False # True, False, None (for reason, see below)
    for c in cursor.get_children():
        if c.kind == cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
            template_params_list.append(("typename", c.spelling))
        elif c.kind == cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            template_params_list.append((_format_type(c.type), c.spelling))
        elif c.kind == cindex.CursorKind.PARM_DECL: # the args in the parenthesis
            # if the prototype doesn't name the argument, then c.spelling is ""
            args_list.append((_format_type(c.type), c.spelling))
        elif c.kind == cindex.CursorKind.CXX_FINAL_ATTR:
            is_final = True
        elif c.kind == cindex.CursorKind.CXX_OVERRIDE_ATTR:
            is_override = True
        # NOTE is_pure_virtual and is_no_throw_bool_or_None are not checked by inspecting c.kind
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
    # 4. for methods: cv-qualifier, "=0", "final", "override"
    postfix_str_list = []
    if cursor.is_const_method():
        postfix_str_list.append("const")
    # if cursor.is_volatile_method(): # defect in clang.index: this method not provided
    #     postfix_str_list.append("volatile")
    if is_final:
        postfix_str_list.append("final")
    if is_override:
        postfix_str_list.append("override")
    if cursor.is_pure_virtual_method():
        is_pure_virtual = True
        postfix_str_list.append("=0")
    exception_spec = cursor.exception_specification_kind
    if exception_spec in noexcept_ExceptionSpecificationKind:
        is_no_throw_bool_or_None = True
        postfix_str_list.append("noexcept")
    elif exception_spec == cindex.ExceptionSpecificationKind.UNEVALUATED:
        # not knowing if it's True or False, this is because per C++11, some functions
        # are non-throwing even if they are not marked with "noexcept" or "throw()" -
        # rule is very complicated: https://en.cppreference.com/w/cpp/language/noexcept_spec
        is_no_throw_bool_or_None = None # not True or False
    postfix_str = ' '.join(postfix_str_list)
    # build prototype string, without template header
    if return_type and cursor.kind != cindex.CursorKind.CONVERSION_FUNCTION:
        accumulate_proto_str = "%s %s" % (return_type, func_name)
    else:
        accumulate_proto_str = func_name
    if cursor.is_virtual_method():
        accumulate_proto_str = "virtual %s" % accumulate_proto_str
    args_repr_list = [ ("%s %s" % item).strip() for item in args_list] # join type and arg name (may be absent)
    proto_str = "%s(%s) %s" % (accumulate_proto_str,
                               ', '.join(args_repr_list),
                               postfix_str)
    proto_str_pretty = proto_str
    if len(proto_str) > 75:
        proto_str_pretty = "%s(\n%s\n) %s" % (accumulate_proto_str,
                                              ",\n".join(["\t%s" % arg for arg in args_repr_list]),
                                              postfix_str)
    # add template header
    proto_str = proto_str if not template_header else template_header + "\n" + proto_str
    proto_str_pretty = proto_str_pretty if not template_header else template_header + "\n" + proto_str_pretty
    # strip redundant whitespaces at both ends
    proto_str = proto_str.strip()
    proto_str_pretty = proto_str_pretty.strip()
    return (
        (proto_str, proto_str_pretty),
        template_params_list, args_list, return_type,
        (is_final, is_override, is_pure_virtual, is_no_throw_bool_or_None)
    )

inheritance_access_specifiers = ["public", "protected", "private"]
def _format_class_proto(cursor):
    template_params_list = []
    base_list = []
    is_final = False
    for c in cursor.get_children():
        if c.kind == cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
            template_params_list.append(("typename", c.spelling))
        elif c.kind == cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            template_params_list.append((_format_type(c.type), c.spelling))
        elif c.kind == cindex.CursorKind.CXX_FINAL_ATTR:
            is_final = True
        elif c.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
            base_spelling = str(c.spelling).replace("class ", "").replace("struct ", "")
            base_spelling = _format_type_spelling(base_spelling)
            inheritance_access_specifier = "public" # the default
            is_virtual_inheritance = False # the default
            # defect in clang.cindex:
            #   no way to check inheritance access and virtual-ness from cindex.Cursor's method,
            #   so I have to go through the tokens
            for t in c.get_tokens():
                if t.kind == cindex.TokenKind.KEYWORD:
                    if t.spelling in inheritance_access_specifiers:
                        inheritance_access_specifier = t.spelling
                    if t.spelling == "virtual":
                        is_virtual_inheritance = True
            base_list.append({
                "access": inheritance_access_specifier,
                "virtual": is_virtual_inheritance,
                "base":  base_spelling
            })
    template_header = ""
    if template_params_list:
        template_header = "template <%s>" % ", ".join(["%s %s" % item for item in template_params_list])
    class_name_str = "class %s" % cursor.spelling
    class_name_str = class_name_str if not is_final else ("%s final" % class_name_str)
    class_name_str = class_name_str if not template_header else "%s %s" % (template_header, class_name_str)
    class_name_str_pretty = class_name_str if not template_header else "%s\n%s" % (template_header, class_name_str)
    return (
        (class_name_str.strip(), class_name_str_pretty.strip()),
        template_params_list,
        is_final,
        base_list
    )

def is_deleted_method(cursor):
    # defect in clang.cindex: no way to check method being marked by "=delete" from
    # cindex.Cursor's method, so I have to go through the tokens
    for t in cursor.get_tokens():
        if (t.kind == cindex.TokenKind.KEYWORD
            and t.spelling == "delete"):
            return True
    return False

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

method_like_CursorKind = [ # method-like
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

array_TypeKind = [
    cindex.TypeKind.CONSTANTARRAY,   # int arr[5]
    cindex.TypeKind.INCOMPLETEARRAY, # int arr[]
    cindex.TypeKind.VARIABLEARRAY,
    cindex.TypeKind.DEPENDENTSIZEDARRAY, # int arr[] = { 'o', 'k', '\0' };
]

pointer_TypeKind = [
    cindex.TypeKind.POINTER,
    cindex.TypeKind.MEMBERPOINTER,
]

def _visit_cursor(c): # visit an AST node (pointed by cursor), returning a symbol dict
    symbol = {} # dict for this symbol
    # part 1. mandated fields
    symbol["spelling"] = "%s" % c.spelling # str
    hierarchy_info = _format_hierarchy(c)
    symbol["hierarchy"] = hierarchy_info[0] # list of dict, might be empty, top-down
    symbol["parent_kind"] = hierarchy_info[1] # str
    symbol["location"] = _format_location(c.location) # str
    symbol["kind"] = _format_syntax_kind(c.kind) # str
    comment_tuple = _format_comment(c.raw_comment)
    symbol["comment"] = comment_tuple[0] # str
    symbol["usage"] = comment_tuple[1] # str
    c_type = c.type
    # part 2. optional fields
    if c.kind in func_like_CursorKind:
        func_proto_tuple = _format_func_proto(c)
        symbol["declaration"] = "%s;" % func_proto_tuple[0][0] # str
        symbol["declaration_pretty"] = "%s;" % func_proto_tuple[0][1] # str
        symbol["is_template"] = True if func_proto_tuple[1] else False# bool
        symbol["template_args_list"] = func_proto_tuple[1] # list of tuple (type, arg name)
        symbol["args_list"] = func_proto_tuple[2] # list of tuple (type, arg name)
        symbol["return_type"] = func_proto_tuple[3] # str or NoneType (e.g. constructor's return type is None)
        specifier_list = []
        if func_proto_tuple[4][0]: # "final" specifier
            specifier_list.append("final")
        if func_proto_tuple[4][1]: # "override" specifier
            specifier_list.append("override")
        if func_proto_tuple[4][2]: # "=0", pure specifier
            specifier_list.append("=0")
        if func_proto_tuple[4][3] == True: # "noexcept" or "throw()" (deprecated since C++11)
            specifier_list.append("noexcept")
        symbol["specifier"] = specifier_list
        # each function-like is either non-throwing or potentially-throwing
        # non-throwing are said to have "no-throw guarantee":
        # C++ exception safety: https://en.wikipedia.org/wiki/Exception_safety
        if func_proto_tuple[4][3] == True:
            symbol["no_throw_guarantee"] = "guaranteed"
        elif func_proto_tuple[4][3] == None:
            symbol["no_throw_guarantee"] = "unevaluated" # what it means: see _format_func_proto()
        else: # False
            symbol["no_throw_guarantee"] = "not_guaranteed"
    elif c.kind in class_like_CursorKind:
        class_proto_tuple = _format_class_proto(c)
        symbol["declaration"] = "%s;" % class_proto_tuple[0][0] # str
        symbol["declaration_pretty"] = "%s;" % class_proto_tuple[0][1] # str
        symbol["is_template"] = True if class_proto_tuple[1] else False# bool
        symbol["template_args_list"] = class_proto_tuple[1] # list of tuple (type, arg name)
        symbol["specifier"] = ["final"] if class_proto_tuple[2] else [] # "final" specifier
        symbol["base_clause"] = class_proto_tuple[3] # list of str
        symbol["is_abstract"] = c.is_abstract_record() # bool
    if c.semantic_parent.kind in class_like_CursorKind:
        symbol["access"] = str(c.access_specifier).split('.')[-1].lower() # str
    if c.kind in val_like_CursorKind + [ cindex.CursorKind.CLASS_DECL, cindex.CursorKind.STRUCT_DECL ]:
        sizeof_type = c_type.get_size()
        symbol["size"] = sizeof_type if sizeof_type > 0 else None # int or NoneType (e.g. type param)
        symbol["POD"] = c_type.is_pod() # bool (POD: Plain Old Data)
        type_kind = c_type.kind
        type_spelling = _format_type(c_type)
        # C++ has a very complicated type system
        if type_kind in [ cindex.TypeKind.TYPEDEF, cindex.TypeKind.ELABORATED ]:
            symbol["type"] = (
                type_spelling, {
                    "type_size": symbol["size"], # int or NoneType
                    # though this type itself is not a type param, yet as a
                    # type alias, its underlying type may be a type param
                    "is_type_alias": True,  # bool
                    "is_type_param": False, # bool
                    "is_array": False,      # bool
                    "is_pointer": False,    # bool
                    # real type, alias resoluted one step only
                    "type_alias_underlying_type": _format_type(c_type.get_declaration().underlying_typedef_type), # str
                    # type alias chain, from this type to completely resoluted type
                    "type_alias_chain": _format_type_alias_chain(c_type), # list of str
                    # real type, alias completely resoluted
                    # if it is not a type param, then it is the same as type_alias_chain[-1].spelling;
                    # if it is a type param, then it is "(type parameter)"
                    "canonical_type": _format_type(c_type.get_canonical()), # str
                }
            ) # tuple of (str, dict)
        elif type_kind == cindex.TypeKind.UNEXPOSED:
            symbol["type"] = (
                type_spelling, {
                    "type_size": symbol["size"], # int or NoneType
                    "is_type_alias": False, # bool
                    "is_type_param": True,  # bool
                    "is_array": False,      # bool
                    "is_pointer": False,    # bool
                    "type_param_decl_location": _format_type_param_decl_location(c_type, symbol["hierarchy"]), # dict
                }
            ) # tuple of (str, dict)
        elif type_kind in array_TypeKind:
            array_size = c_type.get_array_size()
            symbol["type"] = (
                type_spelling, {
                    "type_size": symbol["size"], # int or NoneType, the number of bytes of the whole array
                    "is_type_alias": False, # bool
                    "is_type_param": False, # bool
                    "is_array": True,       # bool
                    "is_pointer": False,    # bool
                    "array_size": array_size if array_size > 0 else None, # int or NoneType, the number of elements
                    "array_element_type": _format_type(c_type.get_array_element_type()), # str
                }
            ) # tuple of (str, dict)
        elif type_kind in pointer_TypeKind:
            symbol["type"] = (
                type_spelling, {
                    "type_size": symbol["size"], # int or NoneType, the number of bytes of the whole array
                    "is_type_alias": False, # bool
                    "is_type_param": False, # bool
                    "is_array": False,      # bool
                    "is_pointer": True,     # bool
                    "pointee_type": _format_type(c_type.get_pointee()), # str
                }
            ) # tuple of (str, dict)
        else:
            symbol["type"] = (
                type_spelling, {
                    "type_size": symbol["size"], # int or NoneType
                    "is_type_alias": False, # bool
                    "is_type_param": False, # bool
                    "is_array": False,      # bool
                    "is_pointer": False,    # bool
                }
            ) # tuple of (str, dict)
    if c.kind in [ cindex.CursorKind.TYPEDEF_DECL, cindex.CursorKind.TYPE_ALIAS_DECL ]:
        # e.g. "typedef float Float;", "using Float = float;"
        symbol["type_alias_underlying_type"] = _format_type(c.underlying_typedef_type) # str, one-step resoluted
        symbol["type_alias_chain"] = _format_type_alias_chain(c_type) # list of str, from this type to completely resoluted
        symbol["canonical_type"] = _format_type(c_type.get_canonical()) # str, completely resoluted
    if c.kind in method_like_CursorKind:
        symbol["is_deleted"] = is_deleted_method(c) # bool
        method_property = []
        if c.is_static_method():
            method_property.append("static")
        if c.is_const_method():
            method_property.append("const")
        if c.is_virtual_method():
            method_property.append("virtual")
        if c.is_pure_virtual_method():
            method_property.append("pure_virtual")
        if c.is_default_method(): # marked by "= default"
            method_property.append("default")
        if symbol["is_deleted"]: # marked by "= delete"
            method_property.append("delete")
        symbol["method_property"] = method_property # list
    if c.kind == cindex.CursorKind.CONSTRUCTOR:
        constructor_property = []
        if symbol["is_deleted"]: # marked by "= delete"
            constructor_property.append("delete")
        if c.is_default_constructor(): # marked by "= default"
            constructor_property.append("default")
        if c.is_copy_constructor():
            constructor_property.append("copy")
        if c.is_move_constructor():
            constructor_property.append("move")
        if c.is_converting_constructor():
            constructor_property.append("converting")
        symbol["constructor_property"] = constructor_property # list of str
    if c.kind == cindex.CursorKind.DESTRUCTOR:
        destructor_property = []
        # destructor cannot be 'static' or 'const'
        if symbol["is_deleted"]: # marked by "= delete"
            constructor_property.append("delete")
        if c.is_default_method(): # marked by "= default"
            destructor_property.append("default")
        if c.is_virtual_method():
            destructor_property.append("virtual")
        if c.is_pure_virtual_method():
            destructor_property.append("pure_virtual")
        symbol["destructor_property"] = destructor_property # list
    if (c.semantic_parent.kind in class_like_CursorKind
        and c.kind == cindex.CursorKind.VAR_DECL):
        # static member is of VAR_DECL kind instead of FIELD_DECL kind
        symbol["static_member"] = True # bool
    if c.kind == cindex.CursorKind.FIELD_DECL:
        symbol["static_member"] = False # bool
    if c.kind == cindex.CursorKind.ENUM_DECL:
        symbol["scoped_enum"] = True if c.is_scoped_enum() else False
        symbol["enum_underlying_type"] = _format_type(c.enum_type)
    if c.kind == cindex.CursorKind.ENUM_CONSTANT_DECL:
        symbol["enum_underlying_type"] = _format_type(c_type.get_declaration().enum_type)
        symbol["enum_value"] = c.enum_value
    return symbol

def _traverse_ast(root_node, target_filename, print_out):
    symbols = [] # list of symbol dicts
    count = 0
    for c in root_node.walk_preorder():
        if str(c.location.file) != target_filename:
            continue # skip header files
        if c.kind not in interested_CursorKinds:
            continue # skip uninterested node
        if not c.spelling:
            continue # skip anonymous node, e.g. anonymous struct declaration
        # visit this node entity, get a dict
        symbol = _visit_cursor(c)
        count += 1
        symbol["id"] = "%s#%d" % (target_filename, count)
        # collect to symbols list
        symbols.append(symbol)
        # print to stdout
        if symbol and print_out:
            _print_to_stdout(symbol)
    return symbols # list of symbol dicts

"""
Input/Output
"""

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

def _is_in_paths(filename, path_list):
    filename = os.path.abspath(filename)
    for path_item in path_list:
        path_item = os.path.abspath(path_item)
        if filename.startswith(path_item):
            return True
    return False

def _get_symbols(target_filename, user_include_paths_str, as_library, to_json):
    include_paths = SYS_INCLUDE_PATHS
    user_include_paths = []
    # user include paths
    if user_include_paths_str: # not empty string
        user_include_paths = [item.strip() for item in user_include_paths_str.split(',')]
        include_paths += user_include_paths
    if not _verify_include_paths(include_paths, user_include_paths):
        sys.exit(1)

    # check printing
    print_out = (not as_library) and (not to_json)

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

    # include stack traverse list, excluding files included by system headers
    include_list = [] # list of dict
    for inc in tu.get_includes():
        included_by = str(inc.location.file) # the file in which the "#include" exists
        # we only want to list files that are 1) included by this target file, or 2) included
        # by a user header (instead of by a system header)
        if (included_by == target_filename
            or _is_in_paths(included_by, user_include_paths)):
            include_list.append({
                "file": str(inc.include), # str, the header file that is included
                "included_at": _format_location(inc.location), # str, the location of "#include"
                "depth": int(inc.depth),  # int, the file directly included by the target file has depth 1
            })
    if print_out:
        print "[includes]\n%s" % '\n'.join([ str(item) for item in include_list ])
        print("[time indexing] %.2f sec" % indexing_time)
        print("[time traverse] %.2f sec" % traversing_time)
    # build result
    result = {
        "symbols": symbols,       # list of symbol dicts
        "includes": include_list, # list of dict
        "errors": errors,         # list of error strings
        "time_indexing": indexing_time,    # float, in seconds
        "time_traversing": traversing_time # float, in seconds
    }
    if to_json:
        import json
        with open(to_json, 'w') as json_file: # overwrite if exists
            json.dump(result, json_file, indent=2, sort_keys=True)
    return result

ordered_keys = [
    "id",          "spelling", "kind",    "hierarchy",
    "parent_kind", "location", "comment", "usage"
]
def _print_to_stdout(symbol):
    # print keys in ordered_keys first, in order; they are present in all symbol dicts
    for key in ordered_keys:
        if key == "hierarchy":
            if not symbol[key]:
                print("::::: hierarchy\n(none)")
            else:
                hierarchy_repr_list = []
                hierarchy_list = []
                for i in range(len(symbol[key])):
                    spelling = symbol[key][i]["spelling"]
                    transparent = symbol[key][i]["transparent"]
                    hierarchy_repr_list.append(spelling if not transparent else ("(%s)" % spelling))
                    hierarchy_list.append(symbol[key][i])
                print("::::: hierarchy\n%s" % ("::" + "::".join(hierarchy_repr_list)))
                for item in hierarchy_list:
                    print item # dict
        elif key == "comment":
            comment = symbol[key]
            print("::::: comment\n%s" % (comment if comment else "(none)"))
        elif key == "usage":
            usage = symbol[key]
            if usage:
                print("::::: usage\n%s" % usage)
        else:
            print("::::: %s\n%s" % (key, symbol[key]))
    # print other keys
    for key, value in symbol.items():
        if key not in ordered_keys:
            if key == "type":
                print("::::: type\n%s\n%s" % (symbol[key][0], symbol[key][1]))
            else:
                print("::::: %s\n%s" % (key, str(value)))
    print("==================")

"""
Library interface
"""

# exposed as library interface, returning a dict
def get(target_filename, user_include_path_list=[]):
    result = _get_symbols(target_filename=args.filename,
                          user_include_paths_str=','.join(user_include_path_list),
                          as_library=True, to_json=None)
    return result


"""
Commandline utility interface
"""

def get_arg_parser():
    arg_parser = argparse.ArgumentParser(description="Generate summary of symbols in a C++ source file",
                                         epilog="if -json is not given, then write result to stdout")
    arg_parser.add_argument("filename", nargs=1, type=str, default="",
                            help="path to file to be parsed")
    arg_parser.add_argument("-i", "--user-include-paths", type=str, default="",
                        help="comma separated list of user include paths, e.g. dir1/dir2,dir3/dir4")
    arg_parser.add_argument("-json", "--to-json", nargs='?', type=str, const="out.json", default=None,
                        help="write to a JSON file (default: out.json)")
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
                 to_json=args.to_json)