# Infinite world generation: Grounding World generation with code-based tool calls for stateful, verifiable environments

> BLUF: Replace hallucination-prone, pure LLM generation with world state stored in a queryable database. Agents interact with the world state with tool calls that query the database.





Inspired by the the ability of MCP agents to call external apps like Figma, we treat the agent's interaction with the game as "tool calls" to a central database of objects and states. This solves some core problems of environment generation: (1) creating an object-orientated, deterministic source of truth on the world state and (2) significantly cutting inference costs which enables batch world generation and quicker error checking.

Specifically, I adapt the architecture of [Agent World Model](https://arxiv.org/pdf/2602.10090) to 2D tasks by replacing black box LLM calls in verification steps of the architecture with deterministic code functions that act as "test cases" that the environments must pass. This addresses the core limitation of the original paper which is prone to hallucination (uses LLMs at all steps of the architecture), reduces inference cost, and increase observability over patterns of generation failure.



**<----------TODO: GIF OF A GENERATED WORLD---------->**



++**Problems we solve for**++

1. **Stateful testing environments**: Testing environments take a long time to generate and importantly, the end result still lacks stateful objects that we can query to understand the status of the game.
2. **Observability over failure points**: Since most environment generation operate off black-box models (ex: LLMs), you cannot pinpoint where the generation failed

++**Goals**++

- **Generate physically grounded objects** - verifiable objects exist in the generated environment that we can query with python functions
- **Generate "interesting" tasks** - environments should be structurally diverse
- **Keep generation lightweight** - perform generation on a Macbook GPU (current generation models require massive compute)
- **Vision policy<->code verification** - translate visual observations (or pixels) to code-verifiable states (or objectives) for the reward function.

++**Architecture summary**++

1. Generator
2. MCP-based environment interaction 
3. Verifier (Deterministic)

## Table of Contents

## Motivation

Generative models have gotten better at creating hyper-realistic and beautiful-looking worlds. However, a common fault is that they are **unverifiable** in physical state. For example, there are no "tree objects" we can query in a generated park. This is a fundamental limitation of video generation models which are *stateless*, their success being attributed to making smart guesses from observations.

## Baselines/Benchmarks

- Neural models
- Procedural generation
- Code world models

## Results

## How to run

--

## Deep dive

### State Generation

The primary goal is to make the state generation/managmeent **form agnostic and extensible to any data management style of other game engines**.

### Verifier

### Current Art

--

## How to start

## References

- [EnvScaler: Scaling Tool-Interactive Environments for LLM Agent via Programmatic Synthesis](https://www.alphaxiv.org/abs/2601.05808?chatId=019ee6f9-b79c-7bdc-b414-529c2bacf331)

