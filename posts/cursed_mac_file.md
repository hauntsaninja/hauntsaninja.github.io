---
title = "A cursed file on macOS"
date = "September 16, 2022"
summary = "In which I learn that files don't always work like files"
---

I like to think that I mostly understand how computers work. But those darn computers still find
ways to surprise me.

For example, I thought I had a pretty good mental model of how files worked, e.g. they represent
data, usually on disk, so you wouldn't expect your shell environment to be able to affect their
contents. But you'd be wrong!

```
λ SYSTEM_VERSION_COMPAT=0 cat /System/Library/CoreServices/SystemVersion.plist
...
	<key>ProductVersion</key>
	<string>12.6.3</string>
...
```

as opposed to:

```
λ SYSTEM_VERSION_COMPAT=1 cat /System/Library/CoreServices/SystemVersion.plist
...
	<key>ProductVersion</key>
	<string>10.16</string>
...
```

It looks like Apple apparently hardcodes this behaviour into `open`:
[https://opensource.apple.com/source/xnu/xnu-7195.81.3/libsyscall/wrappers/open-base.c](https://opensource.apple.com/source/xnu/xnu-7195.81.3/libsyscall/wrappers/open-base.c)
