---
title = "WaPo is very wrong on ChatGPT energy use"
date = "January 6, 2025"
summary = "WaPo's claim on ChatGPT energy use is off by much much more than 1000x"
---

(disclaimer: I've worked at OpenAI since 2020)

The Washington Post claims generating a 100 word email with ChatGPT takes 0.14 kWh of electricity,
resulting in 519 mL of water use
([article link](https://www.washingtonpost.com/technology/2024/09/18/energy-ai-use-electricity-water-data-centers/),
[archive link](https://archive.ph/v83Hl)).

This number is off by many orders of magnitude, maybe around 1000x.<sup><a href="#fn1" id="ref1">1</a></sup>

I'm writing this as a thing I can link to family and friends who ask me about this.

## Cost of electricity

One easy way the Washington Post could have known how mistaken they were: simply compare the cost
OpenAI charges for generating text to the cost of electricity.
You can use OpenAI's GPT-4o model to generate 1 million output tokens at a cost of $5 or $10
per [OpenAI's pricing page](https://openai.com/api/pricing/).

Generating a 100 word email (or about 120 tokens) therefore costs you between 0.06 and 0.12 cents.

If the Washington Post's 0.14kWh number were true, and assuming a [data centre electricity cost of
$0.06 per kWh](https://www.eia.gov/electricity/monthly/update/wholesale-markets.php), it would
take 0.84 cents of electricity to generate a 100 word email.

In other words, for every dollar OpenAI charges you to generate text, OpenAI would be losing
$7 to $14 *just on electricity*, before even taking into account the cost of computer chips,
personnel, operations, partnerships, etc. This is obviously not the case.

## How did they get it so wrong?

The article cites [Making AI Less “Thirsty”: Uncovering and Addressing the Secret Water Footprint
of AI Models](https://arxiv.org/abs/2304.03271) as the source of its methodology.

That paper quotes two sources for energy cost of inference (aka using a model):
- 0.004 kWh per page of text, from the [GPT-3 paper](https://arxiv.org/abs/2005.14165)
- 0.00396 kWh per request, from dividing two numbers in [Estimating the Carbon Footprint of BLOOM](https://arxiv.org/abs/2211.02001)
<sup><a href="#fn2" id="ref2">but see 2</a></sup>

A page of text is conventionally 500 words (600 tokens), so plugging in the
numbers<sup><a href="#fn3" id="ref3">see 3</a></sup>,
Washington Post's number is already off by a factor of 175x from the paper it cites.

There is no explanation I could find for the discrepancy between the Washington Post
and the paper the Washington Post cites — the quoted number is explicitly about inference, not
training. My guess is that they're attempting to account for the difference between GPT-3 and
GPT-4o, so they pull a multiple from a hat, with no discernible connection with any rumoured
or real numbers.

We'll spend the rest of this post talking about why it's actually much cheaper
to use GPT-4o in 2024 than it was to use GPT-3 in 2020, and so even the GPT-3
paper's estimate of 0.0008 kWh per 100 word email is much too high — let alone the number
fabricated by the Washington Post that's 175x higher than that.

While I think the WaPo number is so far off as to be inexcusable, it obviously doesn't help that
OpenAI hasn't published official energy use numbers (in part, because energy use can reveal quite
a lot of proprietary information and because the numbers are changing constantly).

Edit June 2025: Sam Altman included an estimate of ChatGPT energy use per query as an aside
in [one of his blogposts](https://blog.samaltman.com/the-gentle-singularity). That number also
lines up with a 1000x mistake from WaPo, once you correct for the average ChatGPT query being more
than 100 words.

One more quick methodology note: all sources involved are primarily looking at energy usage of just
the GPUs. Somewhat surprisingly, in practice at inference time, the energy draw from other parts of
the system can actually add up meaningfully. But I'll stick apples to apples with WaPo
and its sources and its sources' sources.

## Using models is much cheaper than it was in 2020

When the GPT-3 paper came out, approximately no one cared about generative language models.
Now that people do, there is a lot more incentive to make them efficient. There have been a number
of algorithmic, hardware and engineering improvements in the last five years that make inference
and training much cheaper. I'll give a few random fully publicly known examples, but feel
free to skip past this if it's too much detail.

- The paper [Algorithmic Progress in Language Models](https://arxiv.org/abs/2403.05812) estimates
that the compute required to train a model of a given performance decreases by a factor of 2 every
eight months. This would indicate that today you could train a model equivalent to GPT-3 with
1/128th of the compute cost, only taking into account algorithmic improvements.

- A concrete example of an algorithmic efficiency is better scaling laws that recommend training for
longer, for instance, as described in the [Chinchilla paper](https://arxiv.org/abs/2203.15556). The
Chinchilla paper suggests that if you wanted to train a model with the same capability as GPT-3,
you could train a model that is 3.5x cheaper to use at inference time (with better and better
savings for higher capability levels).

- GPT-3 used Nvidia's V100 chip, which is specced at 130 TFLOPS at 300W TDP. The current generation
Nvidia chip is the H100, which is specced at 1980 TFLOPS at 700W TDP. This is a claimed 6.5x
improvement in performance per watt. In practice this is a bit of an over-claim, but it is
indicative.<sup><a href="#fn4" id="ref4">4</a></sup>

- Engineering can make a substantial difference too, particularly for workloads with a specific
shape. Not all code is equal, for instance, vLLM claims [large performance improvements](https://arxiv.org/abs/2309.06180)
over previous open source inference frameworks.

### ...or just look at what OpenAI charges

GPT-4 was introduced in the OpenAI API in 2023 at the same cost as GPT-3 was originally. Since then,
the cost OpenAI charges to use GPT-4 quality models in the API has fallen by a factor of 6x,
which suggests a lower bound on efficiency improvements.

From the Washington Post's number, you go down 175x to the GPT-3 paper's number. From there, you
go down 6x based on OpenAI's pricing changes. This 6 x 175 alone gets you to the 1000x I claim
in the intro.

### Inference energy use contextualised

I'd estimate that using ChatGPT to generate a 100 word email uses energy roughly similar to:
- Using your phone for 5 minutes
- Using a laptop for 30 seconds
- Lifting a human up a few steps
- Leaving a television off but still plugged in for 10 minutes
- Using a microwave for the time it takes to blink twice
- Using a refrigerator for 5 seconds

One thing to take home: **for a given level of capability, today is the most expensive AI will
ever be**. Writing your emails will continue to get cheaper, likely rapidly.

## What about water usage?

"Making AI less Thirsty"'s water usage numbers are derived from the electricity use numbers.
They essentially multiply the electricity usage by a water usage constant.
<sup><a href="#fn5" id="ref5">5</a></sup>
This means that the water usage estimates are off by the same factor as the
electricity usage estimates.

Indeed, the paper's main contribution appears to be estimating those water usage constants. I have
not independently verified those numbers, but assuming everything else is correct, the water usage
per 100 word email is literally just a few drops.

One other thing I noticed: "Making AI less Thirsty"'s training numbers for GPT-3 come from
[Carbon Emissions and Large Neural Network Training](https://arxiv.org/abs/2104.10350). That paper
already accounts for data centre PUE — the double counting means water usage numbers for training
are inflated by 17% (but this is relatively a small potatoes error when compared to errors
of 100000%).

## What about training?

So far we've focussed just on model usage, because the headline number in the Washington Post
article is explicitly just about the ongoing costs of using a model.

However, the one-time training process for language models is energy intensive.
Whether training a model is worth the energy to do so depends on how much the model gets used.

The 300 million weekly ChatGPT users send over a
[billion messages a day](https://www.theverge.com/2024/12/4/24313097/chatgpt-300-million-weekly-users)
— in addition to all usage of a model via the OpenAI API — so even 10 GWh scale energy use in
training would amortise reasonably.

Good public numbers here are hard to come by, so you'll need to plug in your best guesses, but
you'll likely find the amortised energy cost to be a low multiple of marginal inference cost.

## What about the future?

While for a *given level of capability*, AI is currently the most expensive it will ever be, what
remains to be seen is a) how much capability will increase, b) what demand will be for
these higher levels of capabilities.

For instance, OpenAI's o-series models require more energy at inference time compared to the
traditional GPT models. [Terence Tao](https://en.wikipedia.org/wiki/Terence_Tao) reckons o1 is
"on par with a mediocre but not completely incompetent graduate student".
The recently announced o3 is in the [99.8th percentile on Codeforces](https://www.youtube.com/watch?v=SKBG1sqdyIU),
a competitive programming website. What uses — beyond email writing — will these models and future
even more powerful models unlock?

One MRI scan takes about [20 kWh](https://pubmed.ncbi.nlm.nih.gov/32208096/), or five orders of
magnitude more than a ChatGPT email. How much energy is it worth spending to broaden access
to better medical care?

CERN currently uses about [1.3 TWh of electricity annually](https://www.home.cern/science/engineering/powering-cern)
to power particle accelerators and detectors, much more than generative AI usage today.
How much energy is it worth spending to push the frontiers of science?

---

<sup id="fn1">
1. I'll make the case in this post for 1000x using fully public information. The exact power draw
and token usage numbers I see internally are proprietary information and can be used to infer
proprietary details of OpenAI models.
<a href="#ref1">↩</a></sup>
<br>
<sup id="fn2">
2. The BLOOM paper measures inference cost in a low usage deployment.
The BLOOM paper is really good about contextualising this, talking about how the energy use of
their deployment is just a little bit more than the baseline idle energy use (80% of the energy use
in their 18 day period can be attributed to baseline idle use). The BLOOM paper actually doesn't
even provide the energy per request number since it would be misleading.
<a href="#ref2">↩</a></sup>
<br>
<sup id="fn3">
3. The Washington Post claims 0.14 kWh per 100 words (120 tokens). The GPT-3 paper cited claims
0.004 kWh per page (600 tokens). `(0.14 / 120) / (0.004 / 600) = 175`
<a href="#ref3">↩</a></sup>
<br>
<sup id="fn4">
4. What is definitely an over-claim is this
<a href="https://investor.nvidia.com/events-and-presentations/presentations/presentation-details/2024/NVIDIA-Keynote-at-Computex-2024/default.aspx">Nvidia 2024 presentation</a>
which claims 120x joules per token improvement for GPT models just from using Hopper chips
instead of Volta — not sure where they got that number.
<a href="#ref4">↩</a></sup>
<br>
<sup id="fn5">
5. In the paper, this is Electricity Water Intensity x Power Usage Effectiveness + Water Usage Effectiveness = 3.142 * 1.17 + 0.55
on average in the U.S.
<a href="#ref5">↩</a></sup>
