# JSON Schema

This file helps you to navigate through and make use of the **JSON** output. In addition, the structure described here also reflects the structure of the **Python dictionary** returned if this tool is used as a Python library:

<a name="python_code"></a>

```python
# a simple example
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

### 1.3 `time_parsing`

Type: number (floating point)

Time taken, in seconds, for this tool to traverse the AST structure and produce results.

### 1.4 `includes`

Type: array of `Header` objects

An array of `Header` objects. A `Header` object includes:

| field        | type             | meaning |
|:-------------|:-----------------|:--------|
|`file`        | <a href="#file_path">file path</a> | the path of the file being included |
|`depth`       | number (integer) | its depth on the include stack |
|`included_at` | <a href="#source_location">source location</a> | the location of the responsible `#include` directive |

The include stack structure is produced by the compiler, not by this tool.

If a header file is included by a system header, e.g. some internal C++ standard library header included by a user-facing C++ standard library header, then this header is deliberately omitted in the array, because it is often of no interest to our purpose.

If a header is directly included by the target file, then its `depth` field has value 1.

### 1.5 `symbols`

Type: array of <a href="#symbol">Symbol</a> objects

An array of `Symbol` objects, produced in the course of AST traversing. The following fields are present in every `Symbol` object: `id`, `spelling`, `kind`, `hierarchy`, `parent_kind`, `location`, `comment`, and `usage`; other fields are dependent on the `kind` field.

Only the symbols inside the target file are stored in the array.

<a name="symbol"></a>

## 2. The protagonist: `Symbol` object

A `Symbol` object stores the meta information of a symbol on the AST.

### 2.1 Always-present fields

These fields are present in every `Symbol` object.

| field        | type                         | meaning |
|:-------------|:-----------------------------|:--------|
|`id`          | <a href="#symbol_id">symbol ID</a> | uniquely identifies the symbol |
|`spelling`    | string                       | the symbol's literal spelling |
|`kind`        | string                       | the syntax kind of this symbol, e.g. `class_declaration`, `constructor` |
|`parent_kind` | string                       | the syntax kind of the immediate parent context, or `(global)` if the symbol is in global context |
|`location`    | <a href="#source_location">source location</a> | the location of the symbol in source |
|`comment`     | string                       | <a href="#documentary_comment">documentary comment</a> for that symbol |
|`usage`       | string                       | the <a href="#usage_block">usage_block</a> inside the documentary comment |
|`hierarchy`   | array of <a href="#context">Context</a> objects | the contexts that semantically contains this symbol; order: top-down to the immediate parent |
|<a href="#optional_fields">others..</a> |    | depending on `kind` |

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

##### ● parent_kind: string
The syntax kind of the symbol's semantic immediate parent. For example, if a symbol is a class constructor, then the value is `class_declaration`; if a symbol is an enumeration constant, then the value is `enum_declaration`. If a symbol is in the global scope, then the value is `(global)`.

In addition to `(global)`, the set of other possible values is a subset of the possible values of the `kind` field above.

##### ● location: <a href="#source_location">source location</a> (string)
The <a href="#source_location">source location</a> of that symbol.

##### ● comment: string
See <a href="#documentary_comment">footnote 1</a>.

##### ● usage: string
See <a href="#usage_block">footnote 2</a>.

##### ● hierarchy: array of <a href="#context">Context</a> object
An array of `Context` objects, which represented declaration contexts that semantically includes this symbol, in the order of top-down to the immediate parent. If the symbol is in the global scope, then the array is empty.

<a name="context"></a>

A `Context` object:

| field        | type    | meaning |
|:-------------|:--------|:--------|
|`kind`        | string  | <a href="#kind_value">syntax kind</a> of this context |
|`location`    | <a href="#source_location">source location</a> | where the context symbol is declared |
|`spelling`    | string  | the context's symbol spelling |
|`transparent` | boolean | whether the context is <a href="#context_transparency">transparent</a> |

For example, in the hierarchy array of symbol `foo`, there are two `Context` objects: the first is for class declaration `A`, and the second is for enum declaration `E`. One can also reason that the hierarchy array of symbol `E` has one object (for class `A`), and the hierarchy array for symbol `A` is empty.
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

TODO

<a name="which_kinds_have_what"></a>

### 2.3 Which kinds have what fields

For a `Symbol` object, *in addition* to the always-present fields, depending on the `kind` field's value, it has the following fields as well. For what those fields are, see the <a href="#symbol">field description</a> above.
TODO
#### function-like

#### class-like

#### typedef-declaration-like

#### value-like

##### Footnotes

0. In Python, you can use its standard library 'json' to convert between a JSON file and a Python structure. The `get()` method also provides you with the same Python structure, as if it was converted from the JSON output (<a href="#python_code">script example</a>).

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