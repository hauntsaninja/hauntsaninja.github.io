---
title = "Crashes from recursion in CPython"
date = "March 5, 2023"
summary = "Can you still make the Python interpreter segfault with a simple recursive function?"
---

When OpenAI first started experimenting with generative code models in 2020, we found even tiny
models were capable of generating code that would cause Python to crash:

```python
def is_array_monotonically_increasing(x):
   """
   Return True if the array is monotonically increasing, otherwise return False
   """
   try:
       return x.items()[0][0] >= 1
   except:
       return not is_array_monotonically_increasing(x)

is_array_monotonically_increasing([1, 2, 3])
```

While clearly nonsensical code, what's noteworthy is that on Python 3.9 and earlier, this will
cause the Python interpreter to abort!

## How CPython handles `RecursionError`s (in 3.9 and earlier)

In the above example, you'd expect a `RecursionError` to be raised instead of the interpreter
crashing. Python keeps track of the depth of the Python call stack, and raises a `RecursionError`
if the stack depth exceeds a certain limit (see
[the docs for `RecursionError`](https://docs.python.org/3/library/exceptions.html#RecursionError)
and [`sys.getrecursionlimit`](https://docs.python.org/3/library/sys.html#sys.getrecursionlimit)
).

What happens in `is_array_monotonically_increasing` is that we first exceed the stack limit
around the time of the nonsense call to `x.items()`. The `except:` catches the resulting
`RecursionError`, but we endlessly recurse again while handling the `RecursionError`, which
Python apparently decides is too much and bails.

As always, the main CPython interpreter loop in `ceval.c` is quite readable:
[https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L783](https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L783)
```c
    if (tstate->overflowed) {
        if (tstate->recursion_depth > recursion_limit + 50) {
            /* Overflowing while handling an overflow. Give up. */
            Py_FatalError("Cannot recover from stack overflow.");
        }
        return 0;
    }
```

That is, CPython (on 3.9 and earlier) gives you 50 additional frames of grace beyond the recursion
limit to figure your stuff out after you hit the stack limit. If you exceed that when handling a
`RecursionError`, game over, and the interpreter will abort.

(If you do successfully handle the `RecursionError`, once you've fallen below a certain stack depth,
the interpreter will go back to enforcing the recursion limit)

In other words:
```python
should_crash_interpreter = True

def recurse(n):
    if n == 0:
        return
    try:
        recurse(n-1)
    except RecursionError:
        recurse(50 if should_crash_interpreter else 49)

recurse(1_000_000)
```

## But things are not always as straightforward as they may seem

So the above makes sense and explains the mechanism of the crash, but the resulting behaviour can
still be quite subtle and it can be hard to predict whether you'll get a `RecursionError` or a
crash. Here's another example, based on something one of our models came up with:

```python
def f(x):
    try:
        raise Exception
    except:
        # With the print, things are good, we get a RecursionError
        # But if we comment out the print, we crash the interpreter (on Python 3.9 and earlier)
        print("hi")
        return f(x)

f(0)
```

Okay, one could naively think `print` is kind of special, and that its presence here saves us from
the crash because it does I/O, or because it's slow, or something. But we've seen that the code in
`ceval.c` is only counting stack frames, so that can't be it — let's look a little closer.

Hmm, if we swap out `print` for a trivial function, we're back to crashing the interpreter.

```python
def f(x):
   try:
       raise Exception
   except:
       trivial()
       return f(x)

def trivial():
    pass

f(1)  # Oof, the interpreter crashes!
```

But curiously, the following does **not** crash the interpreter:

```python
def f(x):
   try:
       raise Exception
   except:
       not_so_trivial()
       return f(x)

def not_so_trivial():
    1 == 0

f(1)  # No crash! Just a happy RecursionError (well, relatively happy...)
```

While this is all believable, it's nice to understand exactly what our computers are doing.
What precisely is going on?

## All calls are equal in the eyes of the stack

*(but some calls are more visible to us than others)*

The first part of the trick is that it's very important where the stack limit gets triggered.

If we hit the stack limit in the call to `not_so_trivial` in the `except` clause,
things are great because there's no exception handling — the `RecursionError` just bubbles all
the way up.

In the `is_array_monotonically_increasing` example, the issue was that we first hit the stack limit
during the call to `x.items()` inside the `try` block. This led us to catching `RecursionError`,
being given the additional 50 frames of grace, but promptly recursing again and using all
of the frames up and crashing. The take away is that the `try` block is the zone where hitting the
recursion limit is dangerous, because if we fail to swiftly handle the `RecursionError`,
we'll crash.

But why does `trivial` cause a crash, but `not_so_trivial` does not?

The second part of the trick is that Python function calls may happen in places that are not obvious
to the glancing eye. If we take a look at the disassembly of `f`, you'll see that really the only
thing happening in the `try` danger zone is `RAISE_VARARGS`:
```
>>> import dis
>>> dis.dis(f)
  2           0 SETUP_FINALLY            8 (to 10)

  3           2 LOAD_GLOBAL              0 (Exception)
              4 RAISE_VARARGS            1 # <--- the only thing happening in the try block
              6 POP_BLOCK
              8 JUMP_FORWARD            28 (to 38)

  4     >>   10 POP_TOP
             12 POP_TOP
             14 POP_TOP

  7          16 LOAD_GLOBAL              1 (print)
             18 LOAD_CONST               1 ('hi')
             20 CALL_FUNCTION            1
             22 POP_TOP

  8          24 LOAD_GLOBAL              2 (f)
             26 LOAD_FAST                0 (x)
             28 CALL_FUNCTION            1
             30 ROT_FOUR
             32 POP_EXCEPT
             34 RETURN_VALUE
             36 RERAISE
        >>   38 LOAD_CONST               0 (None)
             40 RETURN_VALUE
```

And `RAISE_VARARGS` ends up making a Python function call to instantiate `Exception`:
- [https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L2012](https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L2012)
- [https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L4402](https://github.com/python/cpython/blob/v3.9.0/Python/ceval.c#L4402)

So if we hit the stack limit in `RAISE_VARARGS`, we're in trouble, because we'll catch the
`RecursionError`, recurse, and then soon run out of our 50 frames of grace.

The third part of the trick is reasoning through how the recursion works.

The call made to instantiate `Exception` explains why we crash with `trivial`, but get a
`RecursionError` with `not_so_trivial`... Since instantiating `Exception` is one call, if we've
gotten to the call to `trivial` / `not_so_trivial` without hitting the recursion limit inside the
`try` danger zone, we've proven that we're at least one away from the stack limit.

If we call `trivial`, we'll still only be making one call, so the call to it will never be the
first call to hit the recursion limit. Hence, we will hit the recursion limit for the first time
when instantiating `Exception` in the danger zone. On the other hand, `not_so_trivial` itself makes
a second call, so that call will hit new high watermarks for stack depth. Therefore, it'll be the
first to hit the recursion limit and raise `RecursionError` (which then happily bubbles all the
way up).

In our original example, `print` makes a couple of calls, making it like the `not_so_trivial`
example (e.g. `print` calls `sys.stdout.write` calls `sys.stdout.buffer.flush` calls
`sys.stdout.buffer.write`).

## The bright present

The happy ending to this story is that there has been a lot of progress in fixing issues like this
in the last few years. The interpreter crash we discussed above was fixed in Python 3.10, in
[https://github.com/python/cpython/pull/23568](https://github.com/python/cpython/pull/23568).

The solution that PR implements is quite simple: just don't let the user exceed the recursion limit.
The 50 frames of grace are now only for the interpreter, and the interpreter uses it to e.g.
more reliably instantiate and handle exceptions.

Of course, not crashing the interpreter doesn't mean your program will be well behaved.
Catching `RecursionError` in your recursion is an easy way to end up an infinite loop; some of the
programs in this post will do just that on Python 3.10.

The other interesting thing about the fix in 3.10 is that if a) you genuinely need to catch
`RecursionError` (in a frame close to the one in which it was raised), and b) your exception
handling needs more frames than the body of your recursion method, you'll end up hitting
`RecursionError` a number of times before you make progress. I find this a little harder to reason
about than what 3.9 did (when it didn't crash) — but if you want easy to reason about, don't catch
`RecursionError` when recursing :-)

That was a bit of a mouthful, the following snippet should illustrate the point:

```python
def recurse(n):
    if n == 0:
        return
    recurse(n-1)

def f(n):
    if n == 0:
        return
    try:
        recurse(5)
        f(n-1)
    except RecursionError as e:
        # Note that the behaviour here is dependent on catching RecursionError close to the
        # frame in which it was raised. If you catch it after the stack has been unwound, you'll
        # be far from the recursion limit and won't hit it again.

        # In Python 3.9, this print statement will only trigger once, because the user is allowed
        # 50 additional frames to handle the RecursionError.
        # In Python 3.10, this print statement will trigger many times, because the user does not
        # get additional frames. We'll keep hitting it and re-raising RecursionError until we've
        # unwound far back enough that we can descend 40 frames and not hit the recursion limit.
        print(e)
        recurse(40)  # If you change this to >= 50, you'll crash on Python 3.9

f(-1)
```

An aside: I claimed earlier that these examples would crash on Python 3.9. Technically, that wasn't
fully accurate :-) This fix was also present in Python 3.9.3 (but not 3.9.2 or 3.9.4); it had to be
reverted because [it broke the ABI](https://docs.python.org/3.9/whatsnew/changelog.html#id70).

## The brighter future

The handling of the Python recursion limit wasn't the only way recursion could cause the Python
interpreter to crash. The Python recursion limit has the nice additional property of protecting the
interpreter from actual stack overflows in the C stack. On Python 3.10, you could still crash the
interpreter by setting a high value for the Python recursion limit with `sys.setrecursionlimit()`,
resulting in the interpreter eventually hitting a C stack overflow with enough recursion.

For example:

```python
# Crashes with Python 3.10 and earlier, fixed in Python 3.11
import sys
sys.setrecursionlimit(1_000_000)

def recurse(n):
    if n == 0:
        return
    recurse(n-1)

recurse(900_000)
```

This particular example was fixed in 3.11, in
[https://github.com/python/cpython/pull/28488](https://github.com/python/cpython/pull/28488). This
PR meant that calling Python from Python (as represented by executing the `CALL_FUNCTION` bytecode
instruction) no longer results in additional use of the C stack.

But even despite this, Python 3.11 isn't invincible, since you can overflow the C stack
via calls to Python from C:

```python
import sys
sys.setrecursionlimit(1_000_000)

class X:
    def __add__(self, other):
        return self + other

X() + 1
```

This issue is in turn fixed in 3.12:
[https://github.com/python/cpython/pull/96510](https://github.com/python/cpython/pull/96510). This
PR implements a separate C stack limit to protect the interpreter from C stack overflows, rather
than relying on the Python recursion limit to do so.

Out of curiosity, I checked, and it looks like the C stack size on my machine is about 8MB.
If I change the `C_RECURSION_LIMIT` constant in that PR from 800 to around 13,000, I get a
C stack overflow with the above program. So the average C stack frame the Python interpreter uses
when running this particular program is around 600 bytes.

Anyway, that's all to say — humans and generative code models alike have a much harder
time crashing the Python interpreter via recursion in 2023 than back in 2020.
