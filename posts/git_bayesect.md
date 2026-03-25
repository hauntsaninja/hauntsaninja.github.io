---
title = "Git Bayesect"
date = "March 22, 2026"
summary = "Git bisection using Bayesian inference"
---

You're probably familiar with `git bisect`, which lets you find a commit that introduces a change
in behaviour via binary search. But what if the change in behaviour is non-deterministic?

For example, say your test suite has gone from always passing to failing 10% of the time.
Or worse, your ML pipeline used to pass an eval 95% of the time, and now it only passes 75% of the time.

Or more befuddlingly, what if you don't even know the probabilities yet? Your test suite used to be
not very flaky, but you've started seeing more failures now. All you know is that something has
changed, but you don't know exactly what or when or by how much.

[git bayesect](https://github.com/hauntsaninja/git_bayesect) is a generalisation of `git bisect`
that uses Bayesian inference to solve this problem.
If your code has started gaslighting you, give it a try!

In this blog post, we'll talk through the math behind how `git bayesect` works, including a fun Beta-Bernoulli conjugacy trick for dealing with unknown probabilities in a principled way.

If you just want to play with the tool and don't want to read a bunch of LaTeX, [check out the repo instead](https://github.com/hauntsaninja/git_bayesect).

## Warmup: we know the probabilities

So we're trying to track down a change in flaky tests.
When we check out a commit and run tests, either it fails (we observe a yes) or it passes (we observe a no).

On the newest commit (index 0), we know the likelihood of observing a yes is $`p_{\text{new}} = 0.8`$.

On the oldest commit (index $`N`$), we know the likelihood of observing a yes is $`p_{\text{old}} = 0.2`$.

We would like to find the commit (index $`B`$) that introduced this change.

That is, we assume there exists some commit with index $`0 \leq B < N`$ such that $`P(\text{observed yes at } b \mid b \leq B) = p_{\text{new}}`$ and $`P(\text{observed yes at } b \mid b > B) = p_{\text{old}}`$.

We start with a probability distribution representing $`P(B = b)`$, the probability of each commit being the one that introduced the change.
Every time we make an observation, we'll update this distribution using Bayes' theorem.

---

**Prior**: `[0.25, 0.25, 0.25, 0.25]`

How likely we think each commit is the culprit, before making this observation. Newest commit is index 0, oldest commit is index 3.

**Observation**: we get a yes on index 2.

**Posterior**: `[0.1, 0.1, 0.4, 0.4]`

The updated probability distribution for $`P(\text{index} = B)`$ after making the observation.

---

We'll quickly work through the update for index 0.

Bayes' theorem says:
$$
P(B = 0 \mid \text{yes}_{i=2}) \propto P(\text{yes}_{i=2} \mid B = 0) \cdot P(B = 0)
$$

If $`B = 0`$, that is, if index 0 introduced the change, then index 2 had the old behaviour. So the likelihood of observing a yes at index 2 is $`P(\text{yes}_{i=2} \mid B = 0) = p_{\text{old}} = 0.2`$.

$`P(B = 0)`$ is our prior that index 0 introduced the change, which from the above table is $`0.25`$. So we scale $`P(B = 0)`$ by $`0.2`$ to get $`0.05`$, the unnormalised posterior.

To turn that back into a probability, we just normalise to ensure that $`\sum_i P(B = i) = 1`$ after the update.
This is equivalent to dividing by the denominator from Bayes' theorem, $`P(\text{yes}_{i=2}) =  p_{\text{new}} \cdot P(B \geq 2) + p_{\text{old}} \cdot P(B \lt 2) = 0.5`$.
So we get $`P(B = 0 \mid \text{yes}_{i=2}) = 0.05 / 0.5 = 0.1`$ as our posterior probability that $`B = 0`$.

We can do a similar calculation for the posterior of the other indices (or for the case where the observation is a no).
This looks pretty simple in code... we just scale by the relevant probability:

```python
# W are weights that encode our prior, as a numpy array

if observation:
    # observed "yes" at `index`
    W[index:] *= p_new
    W[:index] *= p_old
else:
    # observed "no" at `index`
    W[index:] *= (1 - p_new)
    W[:index] *= (1 - p_old)

# normalise to get posterior probability distribution
W /= W.sum()
```

### Priors in practice

In the worked example, we used a uniform prior.
However, in practice, you might have some intuition about where the change was introduced, e.g. based on the files a commit touches.

`git bayesect` supports a few ways of letting you specify priors for commits (e.g. based on filenames or commit text), which results in faster convergence to the culprit commit.

One neat observation: setting the prior for a given commit to zero is akin to `git bisect skip`.

## Commit selection

An important question is: how do we select which commit to test next?

Commit selection is where the "bi" in `git bisect` comes into play.
Naively one could do something similar to bisect, where instead of bisecting the commit range, we bisect the probability mass of our posterior.
That is, we select a commit around 0.5 on the CDF, i.e. the commit $`i`$ for which $`P(B \lt i)`$ is closest to $`P(B \geq i)`$.

However, a more principled thing would be to select the commit that maximises the expected information gain:

$$
\arg\min_i \mathbb{E}[H(P(B \mid \text{observation at } i))] \\
= \arg\min_i P(\text{yes}_i) \cdot H(P(B \mid \text{yes}_i)) + P(\text{no}_i) \cdot H(P(B \mid \text{no}_i))
$$

where $`H`$ is [Shannon entropy](https://en.wikipedia.org/wiki/Entropy_(information_theory)).

A naive implementation would look something like:
```python
for i in range(W):
    # Compute what the posterior would be for yes and no observations at index i, like above
    W_if_yes = posterior(W.copy(), i, observation=True, p_new=p_new, p_old=p_old)
    W_if_no = posterior(W.copy(), i, observation=False, p_new=p_new, p_old=p_old)
    p_yes_i = p_new * W[i:].sum() / W.sum() + p_old * W[:i].sum() / W.sum()
    p_no_i = 1 - p_yes_i
    entropies[i] = p_yes_i * entropy(W_if_yes) + p_no_i * entropy(W_if_no)

selected_index = np.argmin(entropies)
```
This naive version is quadratic, but it's possible to compute this in linear time using prefix and suffix sums, and have it all vectorise nicely — check out the actual code for details.

Expected entropy minimisation is better than picking the median CDF commit for a few reasons:
- It leads us to make an observation at the commit that is expected to improve our probabilistic beliefs the most, as judged by the logarithmic scoring rule
- If our probabilities are asymmetric i.e. $`H(p_{\text{new}}) \neq H(p_{\text{old}})`$, observations are not equally informative, and entropy minimisation will take that into account
- The framing in terms of an objective makes it easier to reason about, especially when we get to the unknown probabilities case

Note that greedy entropy minimisation isn't the optimal commit selection strategy.
It's relatively easy to construct toy examples where you have higher entropy after two steps of greedy entropy minimisation compared to the optimal policy.<sup><a href="#fn1" id="ref1">1</a></sup>

## But we probably don't know the probabilities!

All of the above has assumed we know $`p_{\text{new}}`$ and $`p_{\text{old}}`$ ... but we likely don't actually know these! Sure, we could make a hundred observations at the newest and oldest commits to get a good estimate, but that's information theoretically unsatisfying.

We need to go deeper. Mawwwwr Bayes incoming!

First, some notation.
Given $`\mathcal D`$ representing observations, define:
- $`y_\text{new}(b)`$ as the number of yes observations at commits $`i \leq b`$
- $`n_\text{new}(b)`$ as the number of no observations at commits $`i \leq b`$.
- $`y_\text{old}(b)`$ as the number of yes observations at commits $`i \gt b`$
- $`n_\text{old}(b)`$ as the number of no observations at commits $`i \gt b`$.

In the case where we knew $`p_{\text{new}}`$ and $`p_{\text{old}}`$, the likelihood of the data would have been:

$$
P(\mathcal D \mid B=b, p_{\text{new}}, p_{\text{old}})
=
(p_{\text{new}})^{y_{\text{new}}(b)}
(1-p_{\text{new}})^{n_{\text{new}}(b)}
\cdot
(p_{\text{old}})^{y_{\text{old}}(b)}
(1-p_{\text{old}})^{n_{\text{old}}(b)}.
$$

If your eyes glassed over at that, go back to the Python code snippet.
For each observation we make, we end up scaling our prior by one of four probabilities (`p_new`, `p_old`, `1 - p_new`, `1 - p_old`).
This equation is just what we'd end up multiplying our prior by if we were updating for multiple observations in one go.

But now we don't know values for our $`p_{\text{new}}`$ and $`p_{\text{old}}`$, so we'll have to treat them as random variables, defined by some prior density
$`\pi(p_{\text{new}}, p_{\text{old}})`$. So we end up with a horrible integral to compute the marginal likelihood of the data:
$$
P(\mathcal D \mid B=b)
=
\int_0^1 \int_0^1
P(\mathcal D \mid B=b, p_{\text{new}}, p_{\text{old}})
\;\pi(p_{\text{new}}, p_{\text{old}})
\;dp_{\text{new}}\,dp_{\text{old}}.
$$

...how does one even do that? What would the Python code look like?

### The Beta-Bernoulli conjugacy trick

The trick is that the right choice of prior density $`\pi(p_{\text{new}}, p_{\text{old}})`$ makes the integral tractable.

We choose to use independent Beta priors:
$$
p_{\text{new}} \sim \operatorname{Beta}(\alpha_{\text{new}}, \beta_{\text{new}}), \qquad
p_{\text{old}} \sim \operatorname{Beta}(\alpha_{\text{old}}, \beta_{\text{old}}).
$$

The Beta distribution is quite interpretable: you can think of $`\alpha`$ as the number of yes observations, and $`\beta`$ as the number of no observations. For example, if we set $`\alpha_{\text{new}} = 8`$ and $`\beta_{\text{new}} = 2`$, the expected value of $`p_{\text{new}}`$ would be $`0.8`$.

---

The Beta density is defined as:
$$
f(x; \alpha, \beta)
=
\frac{1}{\mathrm B(\alpha, \beta)}
x^{\alpha-1}(1-x)^{\beta-1}
$$
where $`\mathrm B(\alpha, \beta)`$ is the Beta function, which just normalises the density to ensure it integrates to 1 (and is something Python can compute):
$$
\mathrm B(\alpha,\beta) = \int_0^1 x^{\alpha-1}(1-x)^{\beta-1} dx.
$$

The Beta distribution is [conjugate](https://en.wikipedia.org/wiki/Conjugate_prior) to the Bernoulli distribution, meaning that when we multiply a Bernoulli likelihood by a Beta prior, we get something with the same shape back, just with updated parameters.
The Beta density has a closed form integral, so our marginal likelihood can now be computed in closed form as well.

This is mathe-magic! We'll walk through it.<sup><a href="#fn2" id="ref2">2</a></sup>

---

Okay, now we go back to the horrible integral we had for $`P(\mathcal D \mid B=b)`$. We'll substitute the equation we had for $`P(\mathcal D \mid B=b, p_{\text{new}}, p_{\text{old}})`$, the Beta density for the prior $`\pi(p_{\text{new}}, p_{\text{old}})`$, and factorise.

This will look messy, but it is straightforward:

$$
P(\mathcal D \mid B=b)
=
\int_0^1 \int_0^1
P(\mathcal D \mid B=b, p_{\text{new}}, p_{\text{old}})
\;
\pi(p_{\text{new}}, p_{\text{old}})
\;
dp_{\text{new}}\,dp_{\text{old}}.

\\
=
\int_0^1 \int_0^1
(p_{\text{new}})^{y_{\text{new}}(b)}
(1-p_{\text{new}})^{n_{\text{new}}(b)}
\cdot
(p_{\text{old}})^{y_{\text{old}}(b)}
(1-p_{\text{old}})^{n_{\text{old}}(b)}
\;
\pi(p_{\text{new}}, p_{\text{old}})
\;
dp_{\text{new}}\,dp_{\text{old}}.

\\
=
\left(
\int_0^1
(p_{\text{new}})^{y_{\text{new}}(b)}
(1-p_{\text{new}})^{n_{\text{new}}(b)}
\cdot
\frac{1}{\mathrm B(\alpha_{\text{new}}, \beta_{\text{new}})}
(p_{\text{new}})^{\alpha_{\text{new}}-1}(1-p_{\text{new}})^{\beta_{\text{new}}-1}
\;
dp_{\text{new}}
\right)
\\
\left(
\int_0^1
(p_{\text{old}})^{y_{\text{old}}(b)}
(1-p_{\text{old}})^{n_{\text{old}}(b)}
\cdot
\frac{1}{\mathrm B(\alpha_{\text{old}}, \beta_{\text{old}})}
(p_{\text{old}})^{\alpha_{\text{old}}-1}(1-p_{\text{old}})^{\beta_{\text{old}}-1}
\;
dp_{\text{old}}
\right)
$$

We'll just look at the first integral, since the second one is the same thing with different parameters:

$$
\int_0^1
p^{y_{\text{new}}(b)}
(1-p)^{n_{\text{new}}(b)}
\cdot
\frac{1}{\mathrm B(\alpha_{\text{new}}, \beta_{\text{new}})}
p^{\alpha_{\text{new}}-1}(1-p)^{\beta_{\text{new}}-1}
\;
dp
$$

Collecting exponents,
$$
= \frac{1}{\mathrm B(\alpha_{\text{new}}, \beta_{\text{new}})}
\int_0^1
p^{\alpha_{\text{new}} + y_{\text{new}}(b) - 1}
(1-p)^{\beta_{\text{new}} + n_{\text{new}}(b) - 1}
\;
dp
$$

*And here's the trick*! That integral is just the shape of another Beta function:
$$
= \frac{\mathrm B\!\left(
\alpha_{\text{new}} + y_{\text{new}}(b),
\beta_{\text{new}} + n_{\text{new}}(b)
\right)}{\mathrm B(\alpha_{\text{new}}, \beta_{\text{new}})}
$$

Great, so now we have a closed form:

$$
P(\mathcal D \mid B=b)
=
\frac{\mathrm B\!\left(
\alpha_{\text{new}} + y_{\text{new}}(b),
\beta_{\text{new}} + n_{\text{new}}(b)
\right)}{\mathrm B(\alpha_{\text{new}}, \beta_{\text{new}})}
\cdot
\frac{\mathrm B\!\left(
\alpha_{\text{old}} + y_{\text{old}}(b),
\beta_{\text{old}} + n_{\text{old}}(b)
\right)}{\mathrm B(\alpha_{\text{old}}, \beta_{\text{old}})}
$$

This is a formula we can just stick into Python!
In practice we insert a few logarithms for numerical stability; the update now looks like:
```python
# W is our prior
log_prior = np.where(W > 0, np.log(W), -np.inf)
# yes_new, no_new, yes_old, no_old are arrays as per the functions defined above evaluated at each index
log_likelihood_new = log_beta(alpha_new + yes_new, beta_new + no_new) - log_beta(alpha_new, beta_new)
log_likelihood_old = log_beta(alpha_old + yes_old, beta_old + no_old) - log_beta(alpha_old, beta_old)
# log P(data | index=b) = log_likelihood_left[b] + log_likelihood_right[b]
log_posterior = log_prior + log_likelihood_new + log_likelihood_old
# log_posterior[b] is now numerator of Bayes' theorem, so just normalise by sum(exp(log_posterior))
W = np.exp(log_posterior - logsumexp(log_posterior))
```

---

One more note: we talked about how the Beta distribution is relatively interpretable, with the first parameter representing the number of yes observations and the second parameter representing the number of no observations.

The posterior distribution over $`p_{\text{new}}`$ and $`p_{\text{old}}`$ conditioned on $`B=b`$ are also Beta.

$$
p_{\text{new}} \mid \mathcal D, B=b
\sim
\operatorname{Beta}\!\left(
\alpha_{\text{new}} + y_{\text{new}}(b),
\beta_{\text{new}} + n_{\text{new}}(b)
\right)
$$

This is very nice: we just add our prior parameters to the actual number of yes and no observations we've made so far for a given $`B=b`$ to get the posterior parameters.

In commit selection, our entropy calculation will now have to use the posterior means of $`p_{\text{new}}`$ and $`p_{\text{old}}`$ at commit $`i`$ when calculating the expected entropy after making an observation at $`i`$.

---

## Some summary thoughts

I really enjoy finding the interesting abstractions and ideas lurking at the core of a tool.
I hope you find the tool useful and the ideas interesting!

It's also a fun exercise to relax the assumptions of algorithms you encounter and see what generalisations emerge.
There's plenty assumptions `git bayesect` still makes that could be fun to investigate:
- Observations on each side of the change commit are i.i.d Bernoulli
- There is a single change point
- The user knows an old commit with baseline behaviour
- Greedy entropy minimisation is good enough in practice
- Commits are tested sequentially
- The cost to test each commit is constant
- ... etc ...

---

<sup id="fn1">
1. Consider [0.25, 0.5, 0.25] and p_old = 0, p_new = 0.9. Greedy entropy minimisation will pick the oldest commit, but if you crunch the numbers, you find you'd have been better after the second step picking the middle commit first.
<a href="#ref1">↩</a></sup>
<br>

<sup id="fn2">
2. I had a horrible and slow empirical Bayes' iteration scheme before o3 suggested I look at conjugate priors. Do you ever just find yourself filled with appreciation that math is nice?
<a href="#ref2">↩</a></sup>
<br>
