---
tags: [paper, paradrop, edge, gateway, orchestration]
aliases: [Paradrop]
---

# Paradrop

Source: [Paradrop PDF](../paradrop.pdf)

## Title
*Paradrop: Enabling Lightweight Multi-tenancy at the Network’s Extreme Edge*

## Core contribution
[[papers/paradrop|Paradrop]] shows how to run lightweight, multi-tenant containerized services on edge gateways with backend orchestration and explicit resource controls.

## Reusable primitives
- [[concepts/extreme-edge-service-chutes|Extreme-edge service chutes]]
- local privacy-preserving processing
- cloud-coordinated service orchestration
- explicit CPU / memory / network policy at weak edge nodes

## How it helps an [[LLM]]-over-[[RAN]] system
- It suggests where to place prompt compression, local redaction, enterprise policy checks, retrieval caches, speech preprocessing, or fallback small models.
- It provides a pattern for far-edge service lifecycle management.

## Limits
- It is built around Wi-Fi gateways rather than cellular [[RAN]] nodes.
- It targets lightweight services, not full MEC-grade [[LLM]] execution.
- Its value is mainly at the ingress/far-edge tier of the architecture.

## Key links
- [[concepts/extreme-edge-service-chutes|Extreme-edge service chutes]]
- [[architecture/reference-architecture|Reference architecture]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
