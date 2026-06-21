# Infinite procedural world generation: Grounding
> 

Goals:
- **Generate physically grounded objects** - verifiable objects exist in the generated environment that we can query with python functions
- **Generate "interesting" tasks** - environments should be diverse
- **Keep generation lightweight** - perform generation on a Macbook GPU (current generation models require massive compute)

## Preface
Generative models have gotten better at creating hyper-realistic and beautiful-looking worlds. However, a common fault is that they are **unverifiable** in physical state. For example, there are no "tree objects" we can query in a generated park. This is a fundamental limitation of video generation models which are *stateless*, their success being attributed to making smart guesses from observations.


## Baselines/Benchmarks

- Neural models
- Procedural generation

## Results

--

## How to start