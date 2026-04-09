---
tags: [paper, weaver, ai-ran, gpu, sharing, training]
aliases: [Weaver]
---

# Weaver

Source: [Weaver PDF](../weaver.pdf)

## Title
*Weaver: Foundation Model Training over AI-RAN Compute Infrastructure*

## Core contribution
[[papers/weaver|Weaver]] shows how to safely expose spare [[GPU]] capacity from [[AI-RAN]] infrastructure by embedding a RAN-first compute controller into the MAC scheduler and pairing it with hierarchical elastic training.

## Reusable primitives
- [[concepts/spare-compute-envelope|Spare-compute envelope]]
- RAN-first sharing and deadline protection
- hierarchical inter-site and intra-site adaptation
- macro/micro characterization of spare compute

## How it helps an [[LLM]]-over-[[RAN]] system
- It is the best paper in the set for understanding infrastructure reuse.
- It suggests how spare AI-RAN compute can host compatible AI work without breaking RAN deadlines.
- Its inter-site scheduling ideas inform cross-site overflow and background-task routing.

## Critical warning for inference design
The paper itself makes an important distinction: training is compute-heavy and complements RAN better than [[LLM decode]], which is often memory-bandwidth heavy. That means [[papers/weaver|Weaver]] is a strong fit for training, adaptation, embeddings, and some forms of [[prefill]], but a weaker fit for co-locating interactive decode on the same GPU as RAN PHY.

## Limits
- It studies training, not interactive inference.
- It assumes a GPU-accelerated RAN substrate.
- Its gains depend on the workload being compatible with the exported spare-compute profile.

## Key links
- [[concepts/spare-compute-envelope|Spare-compute envelope]]
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[synthesis/feasibility-matrix|Feasibility matrix]]
