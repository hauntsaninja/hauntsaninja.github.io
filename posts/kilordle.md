---
title = "Solving kilordle"
date = "May 8, 2022"
summary = "Solving a thousand wordles simultaneously with linear programming"
---

If you like puzzles and have logged onto the internet in the last year, you've probably heard of
[wordle](https://en.wikipedia.org/wiki/Wordle).

Aficionados may also be familiar with [quordle](https://www.quordle.com/) where you play
four wordles simultaneously and [octordle](https://octordle.com/) where you play eight.

Last week, I discovered this had been taken to its natural extreme by
[kilordle](https://jonesnxt.github.io/kilordle/), wherein you play a thousand wordles
simultaneously. Typing a thousand words would be pretty tedious, but kilordle has a labour saving
trick: any wordle where you've gotten all five letters green (across previous guesses) is
automatically considered solved.

For example, let's say we're simultaneously solving the mystery words "now", "not", "new", "net",
"low", "lot", "lew", "let". In order to win it would suffice to just guess "now" and "let", since
that's enough to get green letters in all positions of all the mystery words.

```
N O W  N O T  N E W  N E T  L O W  L O T  L E W  L E T
🟩🟩🟩  🟩🟩⬜  🟩⬜🟩  🟩⬜⬜  ⬜🟩🟩  ⬜🟩⬜  ⬜⬜🟩  ⬜⬜⬜
⬜⬜⬜  ⬜⬜🟩  ⬜🟩⬜  ⬜🟩🟩  🟩⬜⬜  🟩⬜🟩  🟩🟩⬜  🟩🟩🟩
```

So the natural question is — how many guesses does it take to solve a kilordle?

To figure this out, we'll need to get a hold of the wordle word lists. These can be found in the
[JavaScript source of the game](https://www.powerlanguage.co.uk/acpt/main.fb033f40.js). Note that
there are two lists:
1) 2315 words that are possible solutions, we'll refer to this list as `TARGETS`.
2) 10657 additional words that you're allowed to guess, we'll refer to this list as `GUESSES`.

First, it's easy to show that you need at least 26 guesses (in the worst case).
```python
>>> [set("abcdefghijklmnopqrstuvwxyz") - set(word[i] for word in TARGETS) for i in range(5)]
[{'x'}, set(), set(), {'q'}, {'j', 'q', 'v'}]
```
That is, every letter is used in the second (and third) position of at least one word in `TARGETS`.
So our 1000 kilordle solutions could contain, e.g., "wAter", "aByss", "sCuba", "iDiot", ...,
"dYing", "aZure". And since each guess can only test a single letter in the second position, we'd
need at least 26 guesses.

And the "worst case" here isn't that unlikely, since 1000 words is an appreciable fraction of the
2315 possible solutions. For example, the least commonly found letters in the second position of
solutions are "j" and "z", with two each. If we're lucky enough to dodge "fjord", we might still
get "eject" and still have to spend a guess on a word with "j" in the second position:
```python
>>> positions_to_words = {
...     (i, c): [w for w in TARGETS if w[i] == c]
...     for i in range(5)
...     for c in "abcdefghijklmnopqrstuvwxyz"
... }
>>> sorted(
...     {k: v for k, v in positions_to_words.items() if len(v) <= 4}.items(),
...     key=lambda x: len(x[1])
... )
[((0, 'x'), []),
 ((3, 'q'), []),
 ((4, 'j'), []),
 ((4, 'q'), []),
 ((4, 'v'), []),
 ((2, 'q'), ['pique']),
 ((4, 'u'), ['bayou']),
 ((1, 'j'), ['fjord', 'eject']),
 ((1, 'z'), ['ozone', 'azure']),
 ((3, 'j'), ['ninja', 'banjo']),
 ((0, 'z'), ['zesty', 'zebra', 'zonal']),
 ((2, 'j'), ['major', 'enjoy', 'rajah']),
 ((3, 'x'), ['proxy', 'epoxy', 'twixt']),
 ((3, 'y'), ['polyp', 'vinyl', 'satyr']),
 ((4, 'z'), ['waltz', 'fritz', 'topaz', 'blitz'])]
```

Two simple observations:
1) We don't care about words as much as we care about letter-positions. If "aaaaa", "bbbbb",
   ..., "zzzzz" were all guessable words, we'd be done.
2) If we have a set of guesses that always solves 2315-rdle, it'll also always solve kilordle.
   From the above, most letter-positions have several words mapping to them, so this isn't an
   unreasonable simplification.

We'll start by doing something simple: greedily choose words based on a simple heuristic. We'll
keep going until we've got words that cover all the letter-positions we need (there are 125
letter-positions we need to cover: 5 × 26 minus the 5 letter-positions seen above not present in
any solutions).

```python
from collections import Counter

def solve():
    position_counts = Counter((i, c) for w in TARGETS for i, c in enumerate(w))
    target_positions = set(position_counts)
    guessed_positions = set()
    guesses = []
    while target_positions - guessed_positions:
        guess = max(
            TARGETS + GUESSES,
            key=lambda w: sum(
                1 / (position_counts[(i, c)] or float("inf"))
                for i, c in enumerate(w)
                if (i, c) not in guessed_positions
            ),
        )
        guesses.append(guess)
        guessed_positions.update((i, c) for i, c in enumerate(guess))
    return guesses

words = solve()
print(f"Found solution of length {len(words)}:")
for w in words:
    print(w)
```

That is, we repeatedly pick words that provide unusual letter-positions that we still need.
It's a pretty natural heuristic to weight a letter-position's value inversely proportional
to how many words provide it.

And sure enough, it spits out a solution of length 34!
```
wagyu niqab hajji pzazz ajwan zuzim orixa yakow affix eques
usher skoff igapo kythe jaxie avows abyss axing adobe acmic
qapik twerp vodka lavvy imbue decad rusma mpret bandh ghyll
stage filth snuck cluck
```

Well, words are fun! I certainly didn't know that "igapo" means "a blackwater-flooded
Amazonian forest".

But how good of a solution is this? Each word is covering 125 / 34 = 3.68 letter-positions on
average — which seems like a good start. But looking a little bit closer, we have 7 words starting
with "a". Feels like we should be able to shave off a word or two pretty easily.

However, this was basically the first thing I tried, and... it proved a surprisingly hard baseline
to beat. I tried a couple different greedy heuristics and tried some stuff on the lines of
simulated annealing and wasn't able to beat 34 words.

So I started running a (slow, terrible, naive) backtracking solver. And while I was waiting, I gave
in. I didn't have much time to spend on this, so I googled to see if there were better solutions
out there. And lo and behold, there is!

Someone on the internet [mentioned using linear
programming](https://www.reddit.com/r/wordle/comments/syuvoq/kilordle_in_43_guesses/i16zgqe)
to find a 30 word solution. (They also mentioned they used Excel to do this... the things people do
with spreadsheets never ceases to amaze me).

I'd completely forgotten about
[linear programming](https://en.wikipedia.org/wiki/Linear_programming)! Many kinds of optimisation
problems can be represented as linear programs. And people have sunk a lot of engineering into LP
solvers — and we can now just throw all of that at kilordle. Finally, like brute force solvers, LP
solvers can tell you whether a solution is optimal, so we don't need to sit around wondering if we
can do any better.

The general formulation of linear programs is: determine the values of some number of variables
such that a) they minimise an objective function that's a linear function of those variables, and
b) satisfy some linear constraints on the values of those variables.

So here's how we'll translate kilordle into a linear program:
- We have one variable for each guessable word. We'll take a value of one to mean that we should
  guess that word and a value of zero to mean that we shouldn't (and we'll constrain these
  variables to be in the range 0 to 1).
- The objective function is the sum of our variables — we want to minimise how many words we guess!
- And of course, we want to make sure we cover all letter-positions. So we'll add a constraint for
  each letter-position that the variables corresponding to words that provide that letter-position
  must sum to at least one.

Putting it together, this is what our linear program looks like (we name our variables by the word
they represent):
```
kilordle:
MINIMIZE
1*aahed + 1*aalii + ... + 1*zymes + 1*zymic
SUBJECT TO
(0,a): aahed + aalii + ... + azyme + azyms >= 1
...
(3,x): ataxy + braxy + deoxy + druxy + epoxy + flaxy + flexi + flexo + orixa
 + prexy + proxy + twixt >= 1
...
(4,z): abuzz + arroz + ... + whizz + wootz >= 1
VARIABLES
0 <= aahed <= 1 Integer
0 <= aalii <= 1 Integer
...
0 <= zymes <= 1 Integer
0 <= zymic <= 1 Integer
```

There's one more constraint visible in this program that we haven't yet talked about. We require
the variables to take on integer values — after all, it doesn't make sense to guess a word 1/2 a
time. But this is not a linear constraint! And this means it's technically not a linear program
either, it's an [integer linear program](https://en.wikipedia.org/wiki/Integer_programming). While
linear programs can be solved in polynomial time, integer linear programs are NP-hard.

This doesn't mean we're dead in the water. First off, solvers are very good! And you can run
solvers with time limits, so it's possible to get good (but potentially suboptimal) solutions.
But also there's a lot you can learn about an integer linear program from its "relaxation" —
the corresponding linear program where you drop the integrality constraints.

For example, solving the relaxation of our kilordle program tells us that we can achieve an
objective function value of 29.047. This is a strictly easier program to solve than our integer
linear program, so 29.047 is a lower bound for our answer. And in our case, our objective function
value must be integer valued (since it's just the sum variables with value 0 or 1), so we can round
up to say confidently that 30 guesses is a lower bound.

Anyway, it turns out an LP solver makes quick work of our program, integral constraints or not.
We use the [PuLP](https://coin-or.github.io/pulp/) library with the default
[CBC](https://github.com/coin-or/Cbc) solver.

```python
# pip install pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum

# create a problem instance
problem = LpProblem("kilordle", LpMinimize)

# define our variables, one for each guessable word
variables = [LpVariable(name=guess, cat="Binary") for guess in GUESSES + TARGETS]
# for the relaxation, we could instead use: LpVariable(name=guess, lowBound=0, upBound=1)

# map letter-positions to variables that cover that letter-position
positions_to_vars = {}
for guess, var in zip(GUESSES + TARGETS, variables):
    for i, c in enumerate(guess):
        positions_to_vars.setdefault((i, c), []).append(var)

# create a constraint for each letter-position to ensure we cover it
target_positions = {(i, c) for word in TARGETS for i, c in enumerate(word)}
for pos in sorted(target_positions):
    problem.addConstraint(lpSum(positions_to_vars[pos]) >= 1, name=f"({pos[0]},{pos[1]})")

# our objective is to minimise the number of guesses
problem.setObjective(lpSum(variables))

# to see a nice representation of the LP
# print(problem)

# solve!
problem.solve()
print(f"Found solution of length {problem.objective.value()}")
for v in problem.variables():
    if v.value():
        print(v.name)
```

And sure enough, we get an optimal solution of length 30. Each word is covering on average 4.17 of
the letter positions we need.
```
abask affix bronc cwtch djinn edger enzym flexo grypt hajji
itchy jambu kvell luvvy mixup ngwee oxbow pzazz qorma rynds
schwa skegg squab tsked updry usque volks whiff ympes zesty
```
