---
title = "Breakpoints in generated Python code"
date = "November 23, 2024"
summary = "How to trick Python into showing you generated code while in a debugger"
---

One of the awesome things about an interpreted language like Python is that you can easily
generate code on the fly using `eval` / `exec`. This can be used for some pretty powerful
metaprogramming, for instance, by libraries like `dataclasses`. A second awesome thing about Python
is that it has built-in breakpointing that lets you walk through your source line by line.

Unfortunately, these two awesome things don't play well together, since `pdb` requires the source
code to be available to print it as you step or to `l / list / ll / longlist` it:
```
λ python
Python 3.13.0 (main, Nov  2 2024, 19:12:16) [Clang 15.0.0 (clang-1500.3.9.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> exec("x = 1\nbreakpoint()\nx = 2\nx = 3")
> <string>(2)<module>()
(Pdb) list
[EOF]
(Pdb) p x
1
(Pdb) next
> <string>(3)<module>()
(Pdb) next
> <string>(4)<module>()
(Pdb) p x
2
(Pdb)
```
In the above, you don't really know where you are or what you're stepping through, all you have is
a line number :-(

Let's fix that!

### `better_exec`

We'll need to use some import system + `inspect` + `linecache` magic to trick Python into finding
the source code for our generated code. Here's what that looks like:

```python
import ast
import os
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util


class ASTLoader(importlib.abc.InspectLoader):
    def __init__(self, code):
        if isinstance(code, ast.AST):
            # Eagerly roundtrip through ast.unparse to ensure line numbers match code
            self.source = ast.unparse(ast.fix_missing_locations(code))
        else:
            self.source = code
        self.source_hash = hashlib.sha1(self.source.encode()).hexdigest()

    def get_code(self, fullname):
        # The filename we generate must:
        # - Be unique (to avoid collisions)
        # - Must not exist (so linecache looks up loader)
        # - Must not start with "<" and end with ">" (so linecache looks up loader)
        # - Must be absolute (so inspect.getsourcefile successfully hits linecache's cache)
        filename = os.path.join(os.sep, "codegen", self.source_hash)
        return compile(self.source, filename, mode="exec")

    def get_source(self, fullname):
        return self.source

    def exec_module(self, module):
        code = self.get_code(module.__name__)
        exec(code, module.__dict__)


def exec_with_source(code):
    loader = ASTLoader(code)
    spec = importlib.machinery.ModuleSpec(loader.source_hash, loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


exec_with_source("x = 1\nbreakpoint()\nx = 2\nx = 3")
```

If you run this, you'll get a much more useful debugging experience:
```
>>> exec_with_source("x = 1\nbreakpoint()\nx = 2\nx = 3")
> /codegen/8d3ee3c3ecb2ec16ec1dbac8fd20d022cc72a67a(2)<module>()
-> breakpoint()
(Pdb) list
  1  	x = 1
  2  ->	breakpoint()
  3  	x = 2
  4  	x = 3
[EOF]
(Pdb) p x
1
(Pdb) next
> /codegen/8d3ee3c3ecb2ec16ec1dbac8fd20d022cc72a67a(3)<module>()
-> x = 2
(Pdb) next
> /codegen/8d3ee3c3ecb2ec16ec1dbac8fd20d022cc72a67a(4)<module>()
-> x = 3
(Pdb)
```
Much better!

### How exactly does that work?

`pdb` locates source code using `linecache.getlines` or `inspect.getsourcelines`.
- [`list` command](https://github.com/python/cpython/blob/v3.13.0/Lib/pdb.py#L1852)
   ```python
   lines = linecache.getlines(filename, self.curframe.f_globals)
   ```
- [`longlist` and `source` commands](https://github.com/python/cpython/blob/v3.13.0/Lib/pdb.py#L2227)

  `inspect.getsourcelines` will call `inspect.findsource` which will in turn eventually call
  `linecache.getlines`, but with some lossiness we'll discuss later.

The `filename` parameter to `linecache.getlines` is straightforward, but what is the scary
`self.curframe.f_globals` about? It's the global variables of the module where the
breakpoint currently is. If `linecache` can't read `filename`, then it goes fishing about in the
module variables to see if it can figure out where the module came from, as per
[the code linked here](https://github.com/python/cpython/blob/v3.13.0/Lib/linecache.py#L178-L191).

The Python import system is very flexible and has some hooks that allow for extremely dynamic
behaviour. Useful in our case is the `get_source` hook that `linecache` attempts to call if it
once it has fished the `importlib` loader out of the module's variables. See
[PEP 302](https://peps.python.org/pep-0302/), the later [PEP 451](https://peps.python.org/pep-0451/)
and the [importlib docs](https://docs.python.org/3/library/importlib.html) for a full rundown.

At this point, you should understand the overall mechanism by which the above `exec_with_source`
works and first three conditions we outlined in `ASTLoader.get_code`. Let's talk about that last
condition — why does the filename need to be absolute?

This is arguably a bug in CPython and one we'll take a closer look at and attempt to fix.

### Figuring out why `inspect.getsourcelines` breaks for frame objects in generated code

This section is kind of gory, so only read if you're interested. The issue is that when `pdb`
calls `inspect.getsourcelines` with a frame object, the frame's `f_globals` gets lost somewhere
along the way, so `linecache`'s attempts to find an `importlib` loader fail.

Note that because `l / list` does not call `inspect.getsourcelines`, you only run into this issue
when you run `ll / longlist` or `source` (and only if you haven't already run `list`, because `list`
will populate `linecache`):
```
(Pdb) ll
*** source code not available
(Pdb) list
< ... happily works ... >
```

Looking at the [first few lines of `inspect.findsource`](https://github.com/python/cpython/blob/v3.13.0/Lib/inspect.py#L1060-L1070), we see the first thing we do is call `inspect.getsourcefile`.
However, `inspect.getsourcefile` tries to be helpful and
[only returns a file when it exists](https://github.com/python/cpython/blob/v3.13.0/Lib/inspect.py#L979).

There are two cases where `inspect.getsourcefile` will happily return a file that doesn't exist.

First, [if the file is cached in `linecache`](https://github.com/python/cpython/blob/v3.13.0/Lib/inspect.py#L977)
It turns out that one of that one of the first things `pdb` will do is print out a prompt.
While printing out that prompt it will
[correctly call `linecache` with the frame globals](https://github.com/python/cpython/blob/09d4c072eb9687bf37c4cd387d5be5008125ff6e/Lib/bdb.py#L624-L625), but before doing so it happens that
[pdb will first convert the filename to an absolute path](https://github.com/python/cpython/blob/09d4c072eb9687bf37c4cd387d5be5008125ff6e/Lib/bdb.py#L42-L57) in just this specific code path. This
explains why we make the filename absolute in `ASTLoader.get_code` — by happy accident, it ensures
we will always hit linecache when running `ll / longlist / source`.

Second, [if it detects the importlib loader hooks](https://github.com/python/cpython/blob/v3.13.0/Lib/inspect.py#L976-L986).
Unfortunately, the attempt to detect an importlib loader goes via `inspect.getmodule`.
`inspect.getmodule` mostly just rummages around in `sys.modules` to find the module object -- but
`exec`-ing generated code does not touch `sys.modules` and so getmodule will fail to find a module
from a frame object in generated code.

Interestingly, it's much easier to get the module's globals from a frame object than it is to get
the module object! We can simply get `f_globals` off the frame object like `pdb` does and use
the module's globals in place of the module object. Something on the lines of:

```diff
     if os.path.exists(filename):
         return filename
     # only return a non-existent filename if the module has a PEP 302 loader
-    module = getmodule(object, filename)
+    if isframe(object):
+        module_dict = object.f_globals
+    else:
+        module_dict = getattr(getmodule(object, filename), "__dict__")
+    if module_dict.get("__loader__") is not None:
-    if getattr(module, '__loader__', None) is not None:
         return filename
-    elif getattr(getattr(module, "__spec__", None), "loader", None) is not None:
+    if getattr(module_dict.get("__spec__"), "loader", None) is not None:
         return filename
```

That change alone is not quite enough to fix the issue. Take a look at
[the next section of `inspect.findsource`](https://github.com/python/cpython/blob/v3.13.0/Lib/inspect.py#L1072-L1076).
`findsource` again calls `inspect.getmodule` on the frame object. We can simply do the same trick
again:

```diff
-    module = getmodule(object, file)
-    if module:
+    if isframe(object):
+        lines = linecache.getlines(file, object.f_globals)
+    elif module := getmodule(object, file):
         lines = linecache.getlines(file, module.__dict__)
     else:
         lines = linecache.getlines(file)
```

With that, we'll much more reliably get our source code!

It was interesting to me how many little quirks and inconsistencies I ran up against in
figuring out in what it took to make this work. In particular, it's less than ideal that `pdb`
attempts to fetch source code three very slightly different ways.
