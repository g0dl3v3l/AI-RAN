---
tags: [paper, chronos, ran, emulation, digital-twin]
aliases: [CHRONOS]
---

# CHRONOS

Source: [CHRONOS PDF](../CHRONOS.pdf)

## Title
*Towards Scalable and Cost-Effective RAN Emulation Leveraging the Public Cloud*

## Core contribution
[[papers/chronos|CHRONOS]] provides a scalable [[RAN]] emulation design that uses [[time virtualization]], slot-level synchronization, and a switch-based forwarding architecture to run high-fidelity experiments in the public cloud.

## Reusable primitives
- [[concepts/ran-digital-twin|RAN digital twin]]
- slot barriers for deterministic coordination
- PHY abstraction through [[FAPI]]
- cloud-scale what-if experimentation

## How it helps an [[LLM]]-over-[[RAN]] system
- It is the right place to test [[concepts/latency-budgeting|latency-budgeting]] policies before deployment.
- It can emulate mobility, handover, and queue buildup while running the same RAN software stack.
- It enables controlled experiments for [[architecture/control-loops|control-loop]] design and admission strategies.

## Limits
- It is an emulation substrate, not a production serving system.
- The paper’s proof-of-concept is limited in scope and omits richer channel modeling.
- It depends on stack-specific hooks and therefore informs methodology more than turnkey deployment.

## Key links
- [[concepts/ran-digital-twin|RAN digital twin]]
- [[architecture/reference-architecture|Reference architecture]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
