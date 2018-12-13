# ccindex

Extract C++ symbols from AST with libclang's Python bindings.

- [x] [schema documentation](schema.md)

#### Input<br>
C++ file, user include paths (optional)

#### Output
- [x] write to stdout (e.g. [example-1.txt](example-out/example-1.txt), [example-2.txt](example-out/example-2.txt), [example-3.txt](example-out/example-3.txt))
- [x] write to JSON file (e.g. [example-1.json](example-out/example-1.json), [example-2.json](example-out/example-2.json), [example-3.json](example-out/example-3.json))
- [x] as Python library: return dict (equivalent to the JSON file's content above)

## 1. Description
This is a script that extracts symbols defined in C++, along with each symbol's meta information:
- syntax kind (e.g. function, class, template, enum),
- type (aware of array, type parameters, and type aliases),
- type alias chain,
- function arguments and template parameters, their types, and default expressions,
- class inheritance,
- class member storage class (`static`),
- function/method properties (static, const, (pure) virtual, delete, copy, move, etc.),
- specifiers (`final`, `override`, `=0`, no-throw exception guarantee),
- scope hierarchy and transparency,
- documentary comment,
- source location,
- include stack,
- etc.

The extracted information could be used to generate API documentations.

> For functions/methods and their templates, the implementation bodies are skipped.

## 2. Required
- [libclang](http://www.llvm.org/devmtg/2010-11/Gregor-libclang.pdf), normally came with a [Clang](http://clang.llvm.org) installation (on macOS, use command `mdfind -name libclang.dylib` to search its path), or you can choose to [build the Clang project](http://clang.llvm.org/get_started.html).
- Python module 'clang', install: `pip install clang` or just copy-paste the [source](https://github.com/llvm-mirror/clang/tree/master/bindings/python/clang).

## 3. Limitation

Runnable on macOS.<br>For Linux, modify `LIBCLANG_PATH_CANDIDATES` and `SYS_INCLUDE_PATHS` in [ccindex.py](ccindex.py).

## 4. Usage
Can be used as a commandline tool or a Python library.

#### 4.1 As a commandline tool
```sh
# help
./ccindex.py -h
# print to stdout:
./ccindex.py path/file.[h|cc] # without user include paths
./ccindex.py path/file.[h|cc] -i UserIncludeDir1/SubDir,UserIncludeDir2
# store as a JSON file:
./ccindex.py path/file.[h|cc] # without user include paths
./ccindex.py path/file.[h|cc] -i UserIncludeDir1/SubDir,UserIncludeDir2 -json out.json
```

#### 4.2 As a Python library
```python
import ccindex
result = ccindex.get("path/file.h", ["UserIncludeDir1", "UserIncludeDir2"])
# the return is a dict:
#     "symbols":         list of symbol dicts (see below)
#     "includes":        list of header info
#     "errors":          list of error strings
#     "indexing_time":   float, in seconds, time taken to index the file
#     "traversing_time": float, in seconds, time taken to traverse the AST
# the symbol dict:
#     these fields are always present:
#            "id", "spelling", "kind", "hierarchy",
#            "parent_kind", "location", "comment", "usage"
#     other fields are optional depending on the kind of each symbol
# For more info on the schema or Python example, see schema.md
```

**NOTE** if the target source file includes user headers, user header directories must be specified with the `-i` option, otherwise some symbols won't be recognized. If there are multiple user header directories, separate them with comma `,` without whitespace.
> user headers: headers that are not in compiler's system header search paths. Normally speaking, user headers are included by `#include ".."`, while system headers are included by `#include <..>`, e.g. standard library and system API.

**NOTE** tested on Python2, but should work with Python3

## 5. Help message
```
$ ./cindex.py -h
usage: ccindex.py [-h] [-i USER_INCLUDE_PATHS] [-json [TO_JSON]] filename

Generate summary of symbols in a C++ source file

positional arguments:
  filename              path to file to be parsed

optional arguments:
  -h, --help            show this help message and exit
  -i USER_INCLUDE_PATHS, --user-include-paths USER_INCLUDE_PATHS
                        comma separated list of user include paths, e.g.
                        dir1/dir2,dir3/dir4
  -json [TO_JSON], --to-json [TO_JSON]
                        write to a JSON file (default: out.json)

if -json is not given, then write result to stdout
```

## 6. Test: produce the example output files
`example-1.cc` has grammar errors;<br>
`example-2.h` and `example-3.cc` don't have grammar errors;<br>
User include path is this directory, represented by `-i .`
```sh
# test stdout
./ccindex.py example-1.cc -i . > example-out/example-1.txt
./ccindex.py example-2.h > example-out/example-2.txt
./ccindex.py example-3.cc -i . > example-out/example-3.txt
# test JSON
./ccindex.py example-1.cc -i . -json example-out/example-1.json
./ccindex.py example-2.h -json example-out/example-2.json
./ccindex.py example-3.cc -i . -json example-out/example-3.json
```

#### License
MIT License

###### EOF