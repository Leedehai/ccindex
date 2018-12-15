# JSON Schema

This file helps you to navigate through and make use of the **JSON** output. In addition, the structure described here also reflects the structure of the **Python dictionary** returned if this tool is used as a Python library:

<a name="python_code"></a>

```python
# a simple Python example
import ccindex
res = ccindex.get("example-1.cc", ["."]) # the target file, the user include path list
for symbol in res["symbols"]:
    if symbol["kind"] == "class_declaration" and symbol["base_clause"]:
        base_locs = [ "%s defined at %s" % (
            base["spelling"], base["definition_location"]) for base in symbol["base_clause"] ]
        print("class %s inherites %s" % (symbol["spelling"], ', '.join(base_locs)))
```

#### Terminologies

###### Compiler
In the following context, "compiler" refers to libclang, the compiler tooling library implemented by the [LLVM/Clang](http://clang.llvm.org) project.

<a name="file_path"></a>

###### File path
A string, either an absolute path, or a relative path with respect to your CWD - current working directory (not to the target file, unless it is in your CWD).

<a name="source_location"></a>

###### Source location
A string that indicates the location of the first character of an entity, in the format of `FilePath:Line:Column` e.g. `~/dev/whatever.cc:1:5`.

For a non-user-defined entity, e.g. primitive type `float` and pointer type `int (*)(int, int)`, their source location strings are empty `""`.

<a name="symbol_id"></a>

###### Symbol ID
A string that uniquely identify a symbol, consisting of the file path and a serial number (starts from 1), in the format of `FilePath#Number`, e.g. `example-1.cc#1`.

## 1. Top-level fields

Each target source file outputs a JSON ([README](README.md)'s usage section). The JSON contains a giant object that has 5 fields: `errors`, `time_parsing`, `time_traversing`, `includes`, and and most importantly, `symbols`.

| field            | type         |
|:-----------------|:-------------|
|`errors`          | array of strings |
|`time_parsing`    | number (floating point) |
|`time_traversing` | number (floating point) |
|`includes`        | array of `Header` objects |
|`symbols`         | array of `Symbol` objects |

### 1.1 errors

Type: array of strings

An array of error strings. In the current compiler's implementation, the format of an error string is `SourceLocation: Severity: Explanation`, where `Severity` is one of `fatal`, `error`, `warning`. Example: `example-1.cc:101:1: error: unknown type name 'Another'`.

The errors are produced by the compiler, not by this tool.

### 1.2 time_parsing

Type: number (floating point)

Time taken, in seconds, for the compiler to parse the translation unit and build an AST.

### 1.3 time_traversing

Type: number (floating point)

Time taken, in seconds, for this tool to traverse the AST structure and produce results.

### 1.4 includes

Type: array of `Header` objects

An array of `Header` objects. A `Header` object includes:

| Header field | type             | meaning |
|:-------------|:-----------------|:--------|
|`file`        | <a href="#file_path">file path</a> | the path of the file being included |
|`depth`       | number (integer) | its depth on the include stack |
|`included_at` | <a href="#source_location">source location</a> | the location of the responsible `#include` directive |

The include stack structure is produced by the compiler, not by this tool.

If a header is not found, the error will be added to the `errors` array above. The root cause is normally (1) the file or its directory does not exist, or (2) it is a user header but the user didn't provide any user include paths when invoking this tool, or the header is not in the provided paths.

If a header file is included by a system header, e.g. some internal C++ standard library header included by a user-facing C++ standard library header, then this header is deliberately omitted in the array, because it is often of no interest to our purpose.

If a header is directly included by the target file, then its `depth` field has value 1.

### 1.5 symbols

Type: array of <a href="#symbol">Symbol</a> objects

An array of `Symbol` objects, produced in the course of AST traversing. The following fields are present in every `Symbol` object: `id`, `spelling`, `kind`, `hierarchy`, `parent_kind`, `location`, `comment`, and `usage`; other fields are dependent on the `kind` field.

Only the symbols inside the target file are stored in the array.

<a name="symbol"></a>

## 2. The protagonist: `Symbol` object

A `Symbol` object stores the meta information of a symbol on the AST.

<a name="always_present_fields"></a>

### 2.1 Always-present fields

These fields are present in every `Symbol` object.

| Symbol field | type                         | meaning |
|:-------------|:-----------------------------|:--------|
|`id`          | <a href="#symbol_id">symbol ID</a> | uniquely identifies the symbol |
|`spelling`    | string                       | the symbol's literal spelling |
|`kind`        | string                       | the syntax kind of this symbol, e.g. `class_declaration`, `constructor` |
|`parent_kind` | string                       | the syntax kind of the immediate parent context, or `(global)` if the symbol is in global context |
|`location`    | <a href="#source_location">source location</a> | the location of the symbol in source |
|`comment`     | string                       | <a href="#documentary_comment">documentary comment</a> for that symbol |
|`usage`       | string                       | the <a href="#usage_block">usage_block</a> inside the documentary comment |
|`hierarchy`   | array of <a href="#context">Context</a> objects | the contexts that semantically contains this symbol; order: top-down to the immediate parent |
|<a href="#optional_fields">others..</a> |    | depending on the `kind` field |

##### ● id: string
A <a href="#documentary_comment">symbol ID</a> string that uniquely identifies the symbol. It consists of the file path and a serial number starting from 1.

An ID is justified because C++ allows name overloading, and using Itanium ABI's [name mangling scheme](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#mangling) results in IDs that are almost unreadable, especially if templates are involved. The source location is not suitable, either, because if two function declarations are the result of one macro instantiation, they will have the same source location.

##### ● spelling: string
The literal spelling of the symbol's name (and name only). No parenthesis, arguments, or template notations are present.

If the symbol is for a constructor, the spelling is the same as the class name; for a destructor, the spelling starts with a tilde, e.g. `~Class`; for an operator overload function or a conversion function, then its spelling starts with `opertor`, e.g. `operator+` and `operator int`.

##### ● kind: string
The syntax kind of the symbol.

<a name="kind_value"></a>

Possible values are (sorted alphabetically):
```
class_declaration     | class_template          | constructor
conversion_function   | destructor              | enum_constant_declaration
enum_declaration      | field_declaration       | function_declaration
function_template     | method                  | namespace
struct_declaration    | type_alias_declaration  | typedef_declaration
variable_declaration
```

For a function template, its `kind` is `function_template`, regardless of it is an independent template or a member template of some <a href="#class_like">class-like</a>. There is no such value `method_template`.

For a static member data, its `kind` is `variable_declaration`; for a non-static member data, its `kind` is `field_declaration`.

`type_alias_declaration` and `typedef_declaration` are different:
```C++
using Int = int;     // type_alias_declaration
typedef float Float; // typedef_declaration
```

##### ● parent_kind: string
The syntax kind of the symbol's semantic immediate parent. For example, if a symbol is a class constructor, then the value is `class_declaration`; if a symbol is an enumeration constant, then the value is `enum_declaration`. If a symbol is in the global scope, then the value is `(global)`.

In addition to `(global)`, the set of other possible values is a subset of the possible values of the `kind` field above.

##### ● location: <a href="#source_location">source location</a> (string)
The <a href="#source_location">source location</a> of that symbol.

##### ● comment: string
See <a href="#documentary_comment">footnote 1</a>.

##### ● usage: string
See <a href="#usage_block">footnote 2</a>.

##### ● hierarchy: array of <a href="#context">Context</a> objects
An array of `Context` objects, which represented declaration contexts that semantically includes this symbol, in the order of top-down to the immediate parent. If the symbol is in the global scope, then the array is empty.

<a name="context"></a>

A `Context` object:

| Context field | type    | meaning |
|:--------------|:--------|:--------|
|`kind`         | string  | <a href="#kind_value">syntax kind</a> of this context |
|`location`     | <a href="#source_location">source location</a> | where the context symbol is declared |
|`spelling`     | string  | the context's symbol spelling |
|`transparent`  | boolean | whether the context is <a href="#context_transparency">transparent</a> |

For example, in the hierarchy array of symbol `foo` (same case for `bar`), there are two `Context` objects: the first is for class declaration `A`, and the second is for enum declaration `E`. One can also reason that the hierarchy array of symbol `E` has one object (for class `A`), and the hierarchy array for symbol `A` is empty.
```C++
// example.cc
class A {
    enum E { foo, bar };
};
```

<a name="optional_fields"></a>

### 2.2 Optional fields

The following fields' presence are dependent on the `kind` field. For which kinds have which fields, see <a href="#which_kinds_have_what">this section</a>.

##### ● (optional) from_macro: string or null
If the symbol is created from a macro instantiation, then `from_macro` is that macro's name spelling, otherwise `null`. For example, in the silly example below, the `from_macro` field of `foo` and `bar` are `CREATE_FUNC`, but that of `baz` is `null`.
```C++
#define CREATE_FUNC(func, op) int func(int a, int b) { return a op b; }
CREATE_FUNC(foo, +)
CREATE_FUNC(bar, -)
int baz(int a, int b) { return a * b; }
```

##### ● (optional) declaration: string
If the symbol is `from_macro` is `null`, then this field is the declaration text of the symbol. Otherwise, this is the macro instantiation text.

##### ● (optional) declaration_pretty: string
Same as above, but is formatted in a way that long line is broken into multiple lines.

##### ● (optional) is_template: boolean
If the symbol is a class template or function template, then this field is `true`, otherwise `false`.

##### ● (optional) template_args_list: array of `TemplateArg` objects
An array of `TemplateArg` objects, representing the template argument list in order. If the symbol is not a template (`is_template` is `false`), then this is an empty array.

A `TemplateArg` object:

| TemplateArg field | type    | meaning |
|:------------------|:--------|:--------|
|`arg_spelling`     | string  | the literal spelling of the template argument |
|`default_expr`     | string or `null` | the default argument expression, `null` if not given |
|`type`             | <a href="#type_object">Type</a> object | the type of this template argument |

##### ● (optional) args_list: array of `Arg` objects
An array of `Arg` objects, representing the argument list - the formal arguments inside the parenthesis - in order. A symbol might have an empty formal argument list.

An `Arg` object:

| TemplateArg field | type    | meaning |
|:------------------|:--------|:--------|
|`arg_spelling`     | string  | the literal spelling of the argument |
|`default_expr`     | string or `null` | the default argument expression, `null` if not given |
|`type`             | <a href="#type_object">Type</a> object | the type of this argument |

##### ● (optional) return_type: <a href="#type_object">Type</a> object or `null`
The return type of the <a href="#function_like">function-like</a> symbol. However, if this symbol is function-like but does not have a return type, i.e. a constructor or destructor, then this field is `null` (note "no return type" is different from "has `void` return type").

##### ● (optional) specifier: array of strings
An array of specifiers added to the <a href="#function_like">function-like</a> or <a href="#class_like">class-like</a> symbol. If no specifiers are present, it is an empty array. The possible values are
```
final | override | = 0 | noexcept
```

According to C++, for a <a href="#class_like">class-like</a>, it is either an array of one element `final` or empty.

Note that `throw()` basically has the same meaning as `noexcept`, and is strongly discouraged [since C++17](https://en.cppreference.com/w/cpp/language/except_spec). Therefore, when listing specifiers, this tool replaces all `throw()` with `noexcept`.

##### ● (optional) no_throw_guarantee: string
A string indicating if no-throw guarantee is provided to a <a href="#function_like">function-like</a>. The possible values are:
```
guaranteed | not_guaranteed | unevaluated
```

A <a href="#function_like">function-like</a> is either guaranteed to not throw any exception, or is not provided with such guarantee. Generally speaking, this guarantee is provided only if `noexcept` or `throw()` exists; however, some complicated [special rules](https://en.cppreference.com/w/cpp/language/noexcept_spec) stipulates that the guarantee is also provided to some that does not one of these two specifiers. If the compiler deems the special rules potentially valid, it will report the `unevaluated` value.

##### ● (optional) access: string
This field is present if the symbol immediately belongs to a <a href="#class_like">class-like</a> context, in other words, its `parent_kind` field holds value `class_declaration` or `class_template`. It represents that symbol's access specifier. The possible values are:
```
public | protected | private
```

##### ● (optional) is_deleted: bool
If the symbol represents a method, including constructor and destructor, then this field is present. This field is `true` if the symbol is marked with `= delete` in the source; otherwise it is `false`.

##### ● (optional) method_property: array of strings
If the symbol represents a method, constructor or destructor, then this field is present, representing some interesting properties. The possible array elements are:
```
static | const | default | delete | virtual | pure_virtual
```

If it is pure virtual, then both `virtual` and `pure_virtual` are present in the array. If `delete` is present, the symbol's `is_deleted` field is set `true`, otherwise `false`. The array can be empty.

##### ● (optional) constructor_property: array of strings
If the symbol represents a constructor, then this field is present, representing some interesting properties. The possible array elements are:
```
default | delete | copy | move | converting
```

The array can be empty. `default` is present only for constructors explicitly marked by `= default`, not for every zero-argument constructor. If `delete` is present, the symbol's `is_deleted` field is set `true`, otherwise `false`. `converting` is present for constructors that can be called with exactly one actual argument - note it could have more than one formal arguments given the others have default expressions.

##### ● (optional) destructor_property: array of strings
If the symbol represents a destructor, then this field is present, representing some interesting properties. The possible array elements are:
```
default | delete | virtual | pure_virtual
```
The array can be empty. `default` is present only for destructors explicitly marked by `= default`. If `delete` is present, the symbol's `is_deleted` field is set `true`, otherwise `false`.

##### ● (optional) base_clause: array of `Base` objects
An array of `Base` objects, each element representing the base class a <a href="#class_like">class-like</a> inherits, in order.

A `Base` object includes:

| Base field | type    | meaning |
|:-----------|:--------|:--------|
|`spelling`  | string  | the literal spelling of the base class |
|`access`    | string  | the access specifier for the inheritance |
|`virtual_inheritance` | boolean | whether the inheritance is virtual |
|`definition_location` | <a href="#source_location">source location</a> | where the base is defined |

If the base is a class template, then the `spelling` will contain the [parameter pack](https://en.cppreference.com/w/cpp/language/parameter_pack), e.g. `TemplateName<int>` (instead of only `TemplateName`). `definition_location` is the location where the base class or base class template is defined.

##### ● (optional) is_abstract: boolean
The field is `true` if the <a href="#class_like">class-like</a> is abstract, i.e. has at least one pure virtual method. Otherwise it is `false`.

Note that a <a href="#class_like">class-like</a> does not need to have a method explicitly marked with `virtual` and `= 0` - if the class-like inherits from an abstract class-like and does not implements all of the inherited pure virtual methods, then this class-like is abstract, too.

##### ● (optional) size: number (integer) or null
The size, in number of bytes, of the <a href="#class_like">class-like</a> or <a href="#value_like">value-like</a>.

If the symbol is for a class template that has a least one type parameter, then this field is `null` as its size is undefined. If the symbol's type is a reference, then this field is the size of the referenced type. If the symbol's type is an array, then this field is the number of bytes in the array, *not* the size of each element *nor* number of elements.

##### ● (optional) POD: boolean
Indicates if the <a href="#class_like">class-like</a> or <a href="#value_like">value-like</a> is [plain old data](https://en.cppreference.com/w/cpp/named_req/PODType). Note: this concept is to be deprecated by C++.

##### ● (optional) type: <a href="#type_object">Type</a> object
A <a href="#type_object">Type</a> object, indicating the type of a <a href="#class_like">class-like</a> or <a href="#value_like">value-like</a> symbol.

##### ● (optional) type_alias_underlying_type: string
The immediate underlying type's literal spelling for a <a href="#type_alias_like">type-alias-like</a>.

This field is the spelling of the underlying type *one-step* resolved. For example, in this example this field of symbol `MyInt` is `Int`, not `int`.
```
typedef int Int;
typedef Int MyInt;
```

##### ● (optional) canonical_type: string
The completely-resolved unerderlying type's literal spelling for a <a href="#type_alias_like">type-alias-like</a>.

Any type-alias chain is resolved. For example, in this example this field of symbol `MyInt` is `int`, not `Int`.
```
typedef int Int;
typedef Int MyInt;
```

If the completely-resolved unerderlying type is a type parameter, this field is `(type_parameter)`. In this case, to retrieve the type parameter's name, one needs to inspect the `type_alias_chain` field's last element.

##### ● (optional) type_alias_chain: array of `TypeAlias` objects
An array of <a href="#type_alias_object">TypeAlias</a> objects, representing the type-alias chain from the type itself, then the one-step resolved type, all the way to the completely-resolved canonical type, in order.

##### ● (optional) static_member: boolean
This field is present (1) if the symbol belongs to a <a href="#class_like">class-like</a> context, in other words, its `parent_kind` field holds value `class_declaration` or `class_template`, and (2) its `kind` field holds value `varaible_declaration` or `field_declaration`. In the conditions above:
- if `kind` is `varaible_declaration`, then this field is `true`, meaning this symbol represents a static member;
- if `kind` is `field_declaration`, then this field is `false`, meaning this symbol represents a non-static member.

##### ● (optional) scoped_enum: boolean
This field is present if `kind` is `enum_declaration` and indicates if this enum is a [scoped enum](https://en.cppreference.com/w/cpp/language/enum).

##### ● (optional) enum_underlying_type: <a href="#type_object">Type</a> object
This field is present if `kind` is `enum_declaration` or `enum_constant_declaration`:
- if `kind` is `enum_declaration`, it indicates the underlying integer type used by the enumeration constants in this enum;
- if `kind` is `enum_constant_declaration`, it indicates the integer type of this enumeration constant.

##### ● (optional) enum_value: number (integer)
The integer value of an enumeration constant.

<a name="type_object"></a>

### 2.3 the `Type` object
C++ has a fairly complex type system, so it deserves to have a fairly complex representation, instead of merely the type name string.

At the top level, a `Type` object includes:

| Type field | type              | meaning |
|:-----------|:------------------|:------------------------------------------|
|`spelling`  | string            | the literal spelling of the type name     |
|`type_info` | `TypeInfo` object | miscellaneous information about this type |

Members of the `TypeInfo` object in the `type_info` field may recursively contain `Type` objects, e.g. a pointer type's `type_info` will contain the type of the pointee.

<a name="type_always_present_fields"></a>

#### 2.3.1 `Type`'s always-present fields
In a `TypeInfo` object, the following fields are always present:

| TypeInfo field | type    | meaning |
|:---------------|:-----------------|:--------|
|`type_size`     | number (integer) | type size, in number of bytes |
|`is_type_alias` | boolean | whether this is a <a href="#type_alias_like">type-alias-like</a> |
|`is_type_param` | boolean | whether this is a type parameter |
|`is_array`      | boolean | whether this is an array |
|`is_pointer`    | boolean | whether this is a pointer |
|`is_function`   | boolean | whether this is a function type |
| <a href="#type_optional_fields">others..</a> | | depends on `is_*` fields |

Those `is_*` fields are mutually exclusive - at most one of them is `true`.

<a name="type_optional_fields"></a>

#### 2.3.2 `Type`'s optional fields
Depending on which one of them is `true`, there are these additional fields:

- if `is_type_alias` is `true`:

| TypeInfo field | type    | meaning |
|:---------------|:-----------------|:--------|
| <a href="#type_always_present_fields">always-present fields..</a> | |  |
|`type_alias_underlying_type` | string | one-step unerderlying type's literal spelling |
|`canonical_type` | string | completely-resolved unerderlying type's literal spelling |
|`type_alias_chain` | array of `TypeAlias` objects | An array of <a href="#type_alias_object">TypeAlias</a> objects, representing the type-alias chain from the type itself, then the one-step resolved type, all the way to the completely-resolved canonical type, in order. |

If the completely-resolved unerderlying type is a type parameter, `canonical_type` is `(type_parameter)`. In this case, to retrieve the type parameter's name, one needs to inspect the `type_alias_chain` field's last element.

- if `is_type_param` is `true`:

| TypeInfo field | type    | meaning |
|:---------------|:-----------------|:--------|
| <a href="#type_always_present_fields">always-present fields..</a> | |  |
|`type_param_decl_location` | `TypeParamDeclLoc` object | location information on this type parameter |

A `TypeParamDeclLoc` object includes:

| TypeParamDeclLoc field | type             | meaning |
|:-----------------------|:-----------------|:--------|
| <a href="#type_always_present_fields">always-present fields..</a> | |  |
|`template_spelling`     | string           | the literal spelling of the template declaration |
|`template_location`     | <a href="#source_location">source location</a> | source location of the template declaration |
|`param_index`           | number (integer) | the type parameter's position in the declaration's template parameter list (starts from 0) |

- if `is_array` is `true`:

| TypeInfo field | type             | meaning |
|:---------------|:-----------------|:--------|
| <a href="#type_always_present_fields">always-present fields..</a> | |  |
|`array_size`    | number (integer) | number of elements in the array |
|`array_element_type` | <a href="#type_object">Type</a> object | the type of array element |

- if `is_pointer` is `true`:

| TypeInfo field | type             | meaning |
|:---------------|:-----------------|:--------|
| <a href="#type_always_present_fields">always-present fields..</a> | |  |
|`pointee_type`  | <a href="#type_object">Type</a> object | the type the pointer points to |

- if `is_function` is `true`:

No additional fields. Only the <a href="#type_always_present_fields">always-present fields</a>.

<a name="type_alias_object"></a>

#### 2.3.3: `TypeAlias` object

A `TypeAlias` object includes:

| TypeAlias field | type | meaning |
|:-----------|:----------|:--------|
|`spelling`  | string    | the literal spelling of the type at the current level |
|`location`  | <a href="#source_location">source location</a> | definition of this type at the current level |

ARTIFACT (FIXEME):
At a level, if the type is a type parameter of some template, the `location` field is an empty string.

<a name="which_kinds_have_what"></a>

### 2.4 Which kinds have what fields: a reference

For a `Symbol` object, *in addition* to the always-present fields, depending on the `kind` field's value, it has the following fields as well. For what those fields are, see the <a href="#symbol">field description</a> above.

<a name="function_like"></a>

#### function-like

`kind`:
```
function_declaration | constructor | destructor | conversion_function | method
function_template
```

For a function template, its `kind` is `function_template`, regardless of it is an independent template or a member template of some <a href="#class_like">class-like</a>. There is no such value `method_template`. To check if a function template is a member, one needs to go through the `hierarchy` field or check if the `access` field exists.

In addition to those <a href="#always_present_fields">always-present fields</a>..

| Symbol fields | (non-class) function or template | constructor | destructor | conversion function | (ordinary) method or template |
|:---------------------------------|:-------------:|:-----------:|:----------:|:-----:|:--------:|
|`from_macro`                      |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`declaration` and `declaration_pretty` |  ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`is_template`                     |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`template_args_list`              |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`args_list`                       |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`return_type`                     |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`specifier`                       |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`no_throw_guarantee`              |       ✓       |  ✓          |  ✓         |   ✓   |   ✓      |
|`is_deleted`                      |               |  ✓          |  ✓         |   ✓   |   ✓      |
|`method_property`                 |               |  ✓          |  ✓         |   ✓   |   ✓      |
|`constructor_property`            |               |  ✓          |            |       |          |
|`destructor_property`             |               |             |  ✓         |       |          |
|`access`                          |               |  ✓          |  ✓         |   ✓   |   ✓      |

<a name="class_like"></a>

#### class-like

`kind`:
```
class_declaration | struct_declaration | class_template
```

In addition to those <a href="#always_present_fields">always-present fields</a>..

| Symbol fields                          | class or struct | template |
|:---------------------------------------|:---------------:|:--------:|
| `declaration` and `declaration_pretty` |      ✓          |    ✓     |
|`is_template`                           |      ✓          |    ✓     |
|`template_args_list`                    |      ✓          |    ✓     |
|`specifier`                             |      ✓          |    ✓     |
|`base_clause`                           |      ✓          |    ✓     |
|`is_abstract`                           |      ✓          |    ✓     |
|`size`                                  |      ✓          |          |
|`POD`                                   |      ✓          |          |
|`type`                                  |      ✓          |          |
|`access`                                |  conditional    |conditional|

`access`: this field is present if `parent_kind` holds value of <a href="#class_like">class-like</a>.

<a name="value_like"></a>

#### value-like

`kind`:
```
variable_declaration | field_declaration | enum_constant_declaration
```

| Symbol fields                          | variable | field | enum constant |
|:---------------------------------------|:--------:|:-----:|:-------------:|
|`size`                                  |    ✓     |   ✓   |      ✓        |
|`POD`                                   |    ✓     |   ✓   |      ✓        |
|`type`                                  |    ✓     |   ✓   |      ✓        |
|`static_member`                         |conditional|   ✓  |               |
|`enum_underlying_type`                  |          |       |      ✓        |
|`enum_value`                            |          |       |      ✓        |
|`access`                                |conditional|conditional|conditional|

`static_member`: this field is present if `parent_kind` holds value of <a href="#class_like">class-like</a>. If this happens, this symbol represents a static member, and its kind is `variable_declaration` instead of `field_declaration`.
> Non-static member's `kind` is `field_declaration`.

`access`: this field is present if `parent_kind` holds value of <a href="#class_like">class-like</a>.

In addition to those <a href="#always_present_fields">always-present fields</a>..

#### enum

`kind`:
```
enum_declaration
```

Note `enum_declaration` is different from `enum_constant_declaration`:
```C++
enum E { // E: enum_declaration
    e1,  // e1: enum_constant_declaration, whose parent context is E
    e2   // e2: enum_constant_declaration, whose parent context is E
};
```

In addition to those <a href="#always_present_fields">always-present fields</a>..

| Symbol fields         | enum |
|:----------------------|:----:|
|`scoped_enum`          |    ✓ |
|`enum_underlying_type` |    ✓ |
|`access`               |conditional|

`access`: this field is present if `parent_kind` holds value of <a href="#class_like">class-like</a>.

<a name="type_alias_like"></a>

#### type-alias-like

`kind`:
```
typedef_declaration | type_alias_declaration
```

```C++
typedef float Float; // typedef_declaration
using Int = int;     // type_alias_declaration
```

In addition to those <a href="#always_present_fields">always-present fields</a>..

| Symbol fields               | typedef | type alias |
|:----------------------------|:-------:|:--------:|
|`type_alias_underlying_type` |      ✓  |    ✓     |
|`type_alias_chain`           |      ✓  |    ✓     |
|`canonical_type`             |      ✓  |    ✓     |
|`access`                     |conditional|conditional|

`access`: this field is present if `parent_kind` holds value of <a href="#class_like">class-like</a>.

##### Footnotes

0. In Python, you can use its standard library 'json' to convert between a JSON file and a Python structure. The `get()` method also provides you with the same Python structure, <a href="#python_code">as if</a> it was converted from the JSON file.

<a name="documentary_comment"></a>

1. Documentary comment (implemented by the compiler, not this tool):
    ```C++
    /**
     * This is a documentaty comment for the symbol on the next line (var1).
     * This comment style can span multiple lines.
     */
    int var1;
    /** This is a documentary comment for the symbol on the next line (var2). */
    int var2;
    int var3; /*< This is a documentaty for the symbol on the same line (var3) */

    /* This is NOT a documentary comment, hence it will NOT be picked up by the compiler */
    int var4;
    int var5; // This is NOT a documentary comment, either */
    ```
<a name="usage_block"></a>

2. Usage block: a special set of contiguous lines inside the documentary comment block.<br>It starts from the comment line that begins with `Usage:`, and ends with the comment line whose next comment line starts with at least 5 dashes in the comment block. If no such ending line is found, it reaches to the end of the comment block. In each line picked up as usage, the whitespaces at both ends are stripped, except for the newline `\n` character.<br>In the example below, the usage block picked up by this tool is `int n = foo(1); // use default arg\nint n = foo(1, 2);`.
    ```C++
    /**
     * This is a documentaty comment for the symbol on the next line (var1).
     * Usage: int n = foo(1); // use default arg
     *        int n = foo(1, 2);
     * ------------
     * This is not part of usage.
     */
    int foo(int a, int b = 0);
    ```
<a name="context_transparency"></a>

3. Context transparency: if a context is transparent, then you don't need a scope resolution operator `::` to refer to the symbols defined in the context from outside. Except for the global scope and [unscoped enum](https://en.cppreference.com/w/cpp/language/enum) (i.e. the vanilla enum), all others are opaque. For example, to refer to class `C`'s method `foo` outside the class, you have to use `C::foo`, because a class context is opaque.

###### EOF
