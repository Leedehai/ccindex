# ccindex

Extract C++ symbols with libclang's Python bindings.

#### Input<br>
C++ file, user include paths (optional)

#### Output
- [x] write to stdout (e.g. [out-1.txt](out-1.txt) and [out-2.txt](out-2.txt))
- [x] write to JSON (e.g. [out-1.json](out-1.json) and [out-2.json](out-2.json))
- [ ] write to SQLite database

## 1. Description
This is a script that extracts symbols defined in C++, along with each symbol's meta information:
- syntax kind (e.g. function, class, function template, class template, enum),
- type (aware of template type parameters and type aliases),
- type alias chain,
- function argument list and template parameter list,
- method properties (e.g. static, const, virtual),
- class member storage class (`static`).
- scope hierarchy,
- documentary comments,
- source location,
- etc.

The extracted information could be used to generate API documentations.

> For functions/methods and their templates, the implementation bodies are skipped.

## 2. Required
- [libclang](http://www.llvm.org/devmtg/2010-11/Gregor-libclang.pdf), normally came with a [Clang](http://clang.llvm.org) installation
- Python module 'clang', install: `pip install clang` or just copy-paste the [source](https://github.com/llvm-mirror/clang/tree/master/bindings/python/clang)

## 3. Limitation

Runnable on macOS.<br>For Linux, modify `LIBCLANG_PATH_CANDIDATES` and `SYS_INCLUDE_PATHS` in [ccindex.py](ccindex.py).

## 4. Usage
Can be used as a commandline tool or a Python library.

#### 4.1 As a commandline tool
```sh
# help
./ccindex.py -h
# print to stdout:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1/SubDir,UserIncludeDir2
# store as a JSON file:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1/SubDir,UserIncludeDir2 -json out.json
# store as a SQLite database:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1/SubDir,UserIncludeDir2 -db out.db
```

#### 4.2 As a Python library
```python
import ccindex
result = ccindex.get("path/file.h", ["UserIncludeDir1", "UserIncludeDir2"])
# the return is a dict:
#     "symbols":         list of symbol dicts (see below)
#     "errors":          list of error strings
#     "indexing_time":   float, in seconds, time taken to index the file
#     "traversing_time": float, in seconds, time taken to traverse the AST
# the symbol dict:
#     these fields are always present:
#            "id", "spelling", "kind", "hierarchy",
#            "parent_kind", "location", "comment", "usage"
#     other fields are optional depending on the kind of each symbol
```

**NOTE** if the source file includes headers, header directories must be specified with the `-i` option, otherwise some symbols won't be recognized.

**NOTE** tested on Python2, but should work with Python3

## 5. Help message
```
$ ./cindex.py -h
usage: ccindex.py [-h] [-i USER_INCLUDE_PATHS] [-json [TO_JSON]]
                  [-db [TO_DATABASE]]
                  filename

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
  -db [TO_DATABASE], --to-database [TO_DATABASE]
                        write to a SQLite database file (default: out.db)

if neither -json nor -db is given, then write result to stdout
```

## 6. Test: produce the example output files
`test-input-1.cc` has grammar errors; `test-input-2.h` doesn't.
```sh
# test stdout
./ccindex.py test-input-1.cc > out-1.txt
./ccindex.py test-input-2.h > out-2.txt
# test JSON
./ccindex.py test-input-1.cc -json out-1.json
./ccindex.py test-input-2.h -json out-2.json
```

#### License
MIT License

###### EOF