# ccindex

Extract API with libclang's Python bindings.

## Description
This is a script that extracts symbols defined in C++, along with each symbol's meta information:
- syntax kind (function, class, method, enum, template, etc.),
- type (aware of template type arguments and typedef),
- source location,
- documentary comments,
- etc.

The extracted information could be used to generate API documentations.

## Required
- [libclang](http://www.llvm.org/devmtg/2010-11/Gregor-libclang.pdf), normally came with a [Clang](http://clang.llvm.org) installation
- Python module 'clang', install: `pip install clang` or just copy-paste the [source](https://github.com/llvm-mirror/clang/tree/master/bindings/python/clang)

## Usage
### as a commandline tool
```sh
# help
./ccindex.py -h
# print to stdout:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2
# store as JSON:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -json out.json
# store as sqlite database:
./ccindex.py path/file.[h|cc]
./ccindex.py path/file.[h|cc] -i UserIncludeDir1,UserIncludeDir2 -db out.db
```

### as Python library
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
#            "spelling", "kind", "hierarchy",
#            "parent_kind", "location", "comment", "usage"
#     other fields are optional depending on the kind of each symbol
```

**NOTE** if the source file includes headers, header directories must be specified with the `-i` option, otherwise some symbols won't be recognized.

**NOTE** tested on Python2, but should work with Python3

## Limitation:
only on macOS; for Linux, modify `LIBCLANG_PATH_CANDIDATES` and `SYS_INCLUDE_PATHS`

## How to run test:
`test-input-1.cc` has grammar errors; `test-input-2.h` doesn't.
```sh
# test stdout
./ccindex.py test-input-1.cc > out-1.txt
./ccindex.py test-input-2.h > out-2.txt
# test JSON
./ccindex.py test-input-1.cc -json out-1.json
./ccindex.py test-input-2.h -json out-2.json
```

## License:
MIT License

## Progress:
- [x] write to stdout
- [x] write to JSON
- [ ] write to sqlite

###### EOF