# AI-RAN Meeting Summary, 15 May 2026

## Overview

The meeting focused on shaping an AI-RAN platform that can use spare cell-site or edge compute without changing how the RAN itself behaves. The group treated the earlier training case as mostly understood, then shifted attention to what is still missing: inference workloads, digital twins, isolation and scheduling across mixed workloads, and the scope of a first prototype that is credible but still manageable. A recurring theme was that the contribution should not be framed as a one-off scheduler for a single workload, but as a clean, modular, AI-RAN-specific platform design that could eventually become an open source reference architecture.

## Context and Overall Aim

- The discussion started from the observation that the hardware substrate is not fully used all the time, so the real question is how to accommodate additional workloads safely on top of spare capacity.
- Prior work on training was treated as a known starting point, not the main unresolved issue in this meeting. Training had already been explored for one specific case, and the group did not want that to dominate the current design discussion.
- The new focus was on broadening the platform to cover:
  - inference workloads,
  - digital twins,
  - and a more general class of non-RAN workloads that might not fit neatly into earlier categories.
- The intended hardware setting is broader than the earlier BGX Spark style setup. The conversation explicitly moved toward a GH200-class server substrate and a fuller view of available resources, including CPU, GPU, memory, and the broader hardware mix.
- The work was repeatedly described as a **system-building exercise**, not primarily an algorithm paper. Scheduler logic matters, but the main claim is about feasibility, modularity, extensibility, and clean architecture.

## Major Technical Themes

- **Inference as the main new workload class**
  - The group split inference into two broad cases:
    - inference offloaded from device to edge, where communication over the air is part of the workload path,
    - inference that simply runs on edge infrastructure as a compute workload.
  - That distinction mattered because device-to-edge inference directly couples radio scheduling with compute scheduling.

- **Digital twin as a first-class part of the AI-RAN picture**
  - The digital twin was described as a controlled environment for learning policies and moving back and forth between a virtual environment and the physical network.
  - The meeting treated this as a meaningful differentiator from narrower AI-for-RAN views that focus only on controllers and accelerators.
  - The digital twin was also framed as useful for online learning, not just offline simulation.

- **General non-RAN workloads**
  - The group wanted the platform to be broad enough to host other workloads, including simpler analytics or server-style workloads such as the NGINX-style examples mentioned from the Concordia paper.
  - At the same time, the prototype does not need to prove every class at once. A simple representative example was considered enough for the first pass.

- **Cross-stack RAN view**
  - The meeting explicitly rejected staying at the very narrow level of only GPU LDPC decoding.
  - The desired framing is cross-stack, covering more of the RAN stack and acknowledging that some workloads will draw on CPU and GPU together.

## Architecture and Platform Direction

- The target is a software layer that sits on top of AI compute hardware and allows RAN and non-RAN workloads to coexist.
- A key architectural baseline was stated clearly:
  - a naive virtualized RAN platform can let many workloads coexist,
  - but without isolation and protection, that is not enough.
- The platform is meant to generalize spare resource exposure across the full hardware picture, not just one accelerator metric.
- The scheduler/interface was described as **bidirectional**:
  - workloads should be able to express intent or constraints,
  - the platform should expose what spare resources are available over time,
  - the scheduler should apportion those resources dynamically.
- The group did **not** want to make RAN a passive consumer of outside control.
  - RAN remains the protected workload.
  - The platform works around it.
  - Other workloads adapt to the spare envelope RAN leaves behind.
- For offloaded inference, the platform still needs a clean interface into the RAN side, because uplink and downlink scheduling can determine whether edge offload meets latency at all.
- The desired high-level shape is modular:
  - workload classes act like pluggable blocks,
  - each class may have its own internal logic,
  - the platform supplies the global skeleton that those blocks fit into.

## Why the Group Framed It This Way

- The discussion pushed back on making this a generic “real-time and non-real-time coexistence” paper.
  - One participant suggested that kind of broader framing as a way to pitch the work.
  - The response was that this would weaken the impact.
  - The AI-RAN setting itself is the selling point because it is emerging, underdefined, and missing a clear platform reference.
- The meeting also spent time on novelty concerns.
  - A challenge was raised that NVIDIA already has orchestration and partitioning systems that look similar at a high level.
  - The response was not to deny that existing ingredients exist, but to argue that the important gap is **RAN awareness** and adaptation to the AI-RAN setting.
- The analogy to earlier programmable RAN work was used to justify this approach.
  - The point was that strong systems papers often reuse existing ingredients,
  - but the hard part is adapting them to a cellular setting and proving that the design actually works under those constraints.
- The group saw the value in a platform because narrow, custom systems for one workload are easier to imagine, but much less useful than a platform that can host multiple workload classes under the same spare-resource logic.
- Another explicit argument was durability:
  - accelerator types may change,
  - workload mix may change,
  - but networks will still be provisioned for worst case demand,
  - so spare headroom will remain a real systems problem.

## RAN Positioning and Protection

- The strongest invariant in the meeting was that **RAN is the first-class citizen**.
- The platform should not optimize user experience inside RAN itself or rewrite RAN control logic for its own sake.
- The working constraint is simpler and stricter:
  - RAN should behave the same way it would if it were running alone.
- In practical terms, that means:
  - the platform protects whatever resources the RAN stack needs,
  - the remaining spare capacity becomes available to other workloads,
  - non-RAN jobs must fit within what they are offered.
- For offloaded inference, some coordination with radio scheduling is still necessary.
  - If the RAN cannot schedule the uplink request and downlink response within the workload’s latency budget, edge offload stops making sense.
  - The meeting treated this as a clean interface problem, not as a reason to redesign the RAN scheduler itself.

## Workload and Runtime Discussion

- The inference-profiling workstream was already looking at the following dimensions:
  - preemption resilience,
  - micro-segmentation,
  - state parking,
  - VRAM compliance.
- The initial workload list had been taken from the CORA paper, including examples such as image segmentation, pose estimation, and language processing.
- The meeting then challenged that as a final taxonomy.
  - Starting from CORA was considered acceptable as a seed.
  - It was not considered enough as the long-term classification scheme.
- A stronger classification logic was proposed:
  - start from **model architecture** or inference structure,
  - then reduce many concrete workloads into a smaller set of underlying categories.
- The architecture-level categories mentioned in the discussion included things like:
  - transformer or autoregressive models,
  - diffusion models,
  - computer vision models,
  - voice-related models,
  - translation,
  - volume rendering.
- A second abstraction layer was then added on top of that:
  - the runtime or system that executes the model,
  - including batching, queueing, operator scheduling, kernel execution, fusion choices, and CPU/GPU coordination.
- This led to an important caution:
  - profiling only the serving/runtime system risks capturing artifacts of those systems rather than the true suitability of the workload class itself.
- The meeting therefore pushed toward a two-level view:
  - first, determine whether the workload class is inherently suitable for this spare-resource AI-RAN setting,
  - then study what kind of runtime/system design is needed to run it well.

## Digital Twin Discussion

- The digital twin was discussed as computationally heavy because realism is expensive.
- Even so, the group saw it as more flexible than hard real-time workloads because it can use **time elasticity**.
  - If it runs in virtual time rather than physical time, it can stretch over spare resources instead of demanding strict wall-clock guarantees.
- That made the digital twin a good candidate for using accelerators opportunistically.
- Existing digital twin systems were described as limited either in realism or in scale.
- The meeting suggested that a co-located, high-realism digital twin that works in tandem with the physical network would be a real addition to the AI-RAN story.
- The digital twin was also deliberately de-emphasized as an algorithm paper topic in this meeting.
  - The point here was not to invent new learning algorithms,
  - but to show that the system can host and support that mode of operation.

## Prototype Scope

- The group repeatedly narrowed the first prototype to a **single site** or **single node** setting.
- That narrowing was not treated as a concession.
  - It was treated as the right first contribution.
  - A single site was said to be enough to show value.
- Multi-node or multi-site deployment was acknowledged as relevant in reality, especially since radio deployments are distributed.
- Still, the meeting explicitly parked that for later.
  - The message was that distributed progression guarantees, slicing across nodes, and multi-server orchestration can be added later once the single-node skeleton is clear.
- The prototype only needs enough workload variety to show generality.
  - A training case already exists as prior context.
  - Inference is now the main new class.
  - A simple extra workload, such as an NGINX-style workload, would be enough to represent the “other workloads” category.
- The end-of-August milestone was used as the practical forcing function for scope control.

## Runtime, Isolation, and Local Coexistence Discussion

- Container-based coexistence came through as the most practical local starting point.
  - Linux container and cgroup-style control was explicitly cited as useful for partitioning and isolation.
- This approach was attractive because:
  - it is already available,
  - it fits naturally with software packaging,
  - reconfiguration cost was described as very low.
- At the same time, the meeting did not pretend the hard parts were solved.
  - Strict GPU spatial partitioning is hard for some workloads.
  - Weaver-era techniques do not transfer cleanly to every case.
  - Some tasks may need preemption and controlled slow-down rather than clean spatial isolation.
- One evolving design idea was:
  - monitor resource use,
  - detect when a workload exceeds its offered boundary,
  - briefly pause or preempt it,
  - then resume once the system is back inside the intended envelope.
- Another important conceptual shift was that the scheduler should not depend on perfect prediction of what a task wants.
  - Instead, the platform offers a resource envelope,
  - workloads operate within what they are given,
  - and the system updates those offers over time.
- A partially working local coexistence prototype was mentioned.
  - The speaker said the hosting setup is already running,
  - other workloads can coexist,
  - and the RAN-side integrator remains protected,
  - though the global scheduler still needs polishing.

## Comparison with Prior Work and Existing Systems

- The meeting made a distinction between three kinds of prior art:
  - earlier internal work such as Weaver,
  - prior edge or AI-RAN style systems that distribute tasks but are not truly RAN-aware,
  - and NVIDIA-style orchestration platforms that manage GPU, CPU, and memory globally but do not solve the AI-RAN-specific control and protection problem.
- The proposed work was not framed as “ignore prior work and build a new stack from zero.”
- Instead, the stated intent was:
  - use what already exists where it makes sense,
  - then adapt and tailor it to the AI-RAN setting,
  - especially around RAN protection, workload coexistence, and platform-level modularity.
- That is also why the open source reference architecture angle mattered so much.
  - The group’s belief was that if the design is clean and the prototype is convincing, outside users will adopt it the way earlier open systems work gained traction.

## Reasoning Behind the Main Decisions

- **Why keep the focus on AI-RAN, not a generic OS paper?**
  - Because the setting is what gives the work urgency and potential adoption.
  - A generic framing would make it easier for others to say the system is not really for AI-RAN.
- **Why keep RAN untouched?**
  - Because the whole proposition depends on proving that spare compute can be used without degrading the protected communication workload.
- **Why start at a single node?**
  - Because that is enough to demonstrate the core architecture and already counts as a contribution.
  - The distributed case adds complexity that can obscure the first result.
- **Why care so much about modularity?**
  - Because the field is early, workload types will keep changing, and a platform has more staying power than a custom scheduler for one model family.
- **Why discuss model architecture and runtime separately?**
  - Because the system must capture the true character of workloads, not just quirks of one serving engine.

## Open Questions and Unresolved Issues

- How should the workload taxonomy finally be organized?
  - By paper examples,
  - by model architecture,
  - by runtime design,
  - or by a layered combination of those views?
- How should GPU boundary enforcement work in practice for workloads that do not support clean spatial partitioning?
- How much application modification is acceptable for non-RAN workloads?
  - The ideal case is near-zero application changes with only shim-level adaptation, but that is still a design goal rather than a proven result.
- How should user/session identity be mapped cleanly across layers when a workload depends on RAN scheduling?
- What is the right abstraction vocabulary?
  - The meeting repeatedly got stuck on terms such as application, workload class, instance, slice, and sub-container.
- What should the evaluation plan look like?
  - This was acknowledged, but intentionally deferred until the design is clearer.
- How much of the distributed, multi-node problem can safely be postponed without weakening the architecture?
- How much existing NVIDIA-style infrastructure can be reused before the design becomes too tied to one vendor stack?

## Risks and Constraints

- The platform may be technically compelling but still depend on outside ecosystem factors, such as how standards and deployments evolve.
- A weak framing could undersell the contribution even if the system is good.
- If the taxonomy for inference stays too tied to one paper or one serving engine, the analysis may not generalize well.
- GPU sharing remains a real technical constraint, especially for workloads that do not admit clean spatial boundaries.
- Multi-node concerns can quickly consume the project if brought in too early.
- Terminology and schematic clarity are not cosmetic issues here. The meeting showed that unclear abstractions can make the design look more complicated than it really is.

## Responsibilities and Ownership

- **Dheeraj**
  - Owns the new inference-focused thread.
  - Is already profiling inference workloads and runtimes.
  - Was encouraged to broaden the taxonomy beyond the current CORA-derived starting point.

- **Yufeng**
  - Is tied to the GH200 deployment and stack bring-up work.
  - Is associated with the generalized scheduler or pub-sub style interface across workloads.
  - Had sent an update already, but the group did not get to review it in full before time ran out.

- **The platform-design owner**
  - Is focused on the platform “glue,” local coexistence, scheduler/resource-tracker structure, and the prototype skeleton that other modules can plug into.
  - Was pushed to simplify terminology, make the design more schematic, and show how the architecture supports others’ work.

- **Leyang**
  - Raised the framing question about how best to pitch the work.
  - Agreed to send references that might help sharpen the architecture/system framing.
  - Contributed the argument that existing systems literature should be used as background, but not allowed to erase the AI-RAN-specific setting.

## Next Steps

- Merge the separate slide decks into a single shared deck and keep evolving that as the common artifact for the project.
- Put the shared deck link in the Teams channel so the group can use it for offline coordination.
- Bring the architecture back in a clearer, more coherent schematic form, especially the platform skeleton that other modules will sit on.
- Continue the inference profiling work, but refine the taxonomy so it is not locked to the CORA examples alone.
- Separate model-level workload structure from runtime-engine behavior in the profiling methodology.
- Follow up on the RAN-application interaction references that were mentioned during the discussion.
- Review Yufeng’s update in the next session, since that part was cut short by time.
- Hold a follow-up meeting in the next few days, with Monday or Wednesday suggested.
- Keep the first meaningful prototype bounded to the single-node or single-site case.
- Work toward an end-of-August target for the first coherent design and prototype story.

# AI-RAN Meeting Summary, 22 May 2026

## Overview

This meeting, captured across two back-to-back transcript files on the same afternoon, had two main threads. The first was a deep review of the digital-twin direction, where the discussion moved away from implementation-first reporting and toward a stronger research framing centered on design alternatives, preemptibility, resource adaptation, and clearer justification for why the digital twin matters as a co-located non-RAN workload in AI-RAN. The second was a practical discussion about how to position the Spotlight anomaly-detection pipeline for the campus monitoring stack, including a recommendation to stay with a single-cell interpretation for now so that it can become a credible demo and a concrete application example in the monitoring-system paper.

## Context and Overall Aim

- The digital-twin thread was framed as a workload-design problem, not just an emulator-integration problem.
- The core ambition was to understand how a full-stack digital twin can coexist with spare and fluctuating compute while still remaining useful for AI-RAN tasks such as policy exploration and network understanding.
- The discussion repeatedly emphasized that the right contribution is not “we implemented something that runs,” but “we compared the design space, justified the chosen architecture, and then built the right thing.”
- On the monitoring side, the immediate goal was not to redesign Spotlight into a general multi-cell anomaly framework. The more urgent goal was to fit it cleanly into Campus 5G as an operational application, support the monitoring-system workstream, and create something that can be shown to visitors and referenced in a short-turnaround paper.
- A secondary but important coordination theme was to reduce anxiety around external workshop deadlines and keep the technical work aligned with the actual research priorities rather than with perceived time pressure.

## Digital Twin Requirements and Research Question

- Dheeraj opened by laying out the digital twin as something that must stay closely tied to the real compute and the real network, rather than living in a purely isolated virtual world.
- A mandatory requirement identified in the discussion was a working interface between the real RAN / real network and the digital RAN / virtual environment.
  - Real-world parameters and measurements need to flow into the virtual environment.
  - Policies or decisions derived in the virtual environment may need to flow back and influence the real system.
- The digital twin was therefore framed as relevant not just because it simulates a network, but because it participates in a feedback loop with the physical deployment.
- The core research question was described as how to adapt a large, full-stack digital workload to available resources so that it can deliver reliable insight without undermining the protected communication workload.
- Three broad strategy buckets were presented for answering that question:
  - selective fidelity,
  - multi-fidelity system architecture,
  - distributed and adaptive resource management.

## Design Ideas Presented for the Digital Twin

- **Selective fidelity**
  - The main intuition was that not every physical component needs the same simulation fidelity all the time.
  - The proposal was to preserve high realism for the components that matter most to the behavior being studied, such as channel dynamics and interference behavior.
  - Less critical components could be approximated more aggressively in order to reduce computational cost.
  - Full physical detail everywhere was treated as too expensive if the twin is meant to coexist with other workloads on spare infrastructure.
  - The selective-fidelity idea was therefore positioned as a way to trade fidelity against cost without giving up realism where it matters most.

- **Multi-fidelity system architecture**
  - A gap was identified between higher-level system emulation and lower-level physical simulation.
  - Existing tools were described as each covering only part of the problem:
    - system-level RAN emulators cover end-to-end behavior but abstract away low-level physical realism,
    - physical-layer tools can be realistic but do not by themselves give a full-stack or system-level digital-twin view.
  - The proposed response was to combine a system-level RAN framework with a more realistic physical-layer backend so that the twin can remain full-stack while still becoming more physically grounded where needed.
  - In follow-up questioning, it was clarified that this was not meant to imply full highest-fidelity physics everywhere. Instead, some parts of the system would be simulated at finer granularity while others would remain more abstract.

- **Distributed and adaptive resource management**
  - The design also proposed distributing work across nodes when resources are available elsewhere.
  - A partitioned ray-tracing idea was introduced as a way to split a large and expensive simulation task into smaller independent regions that can run on different workers or nodes and later be combined.
  - This was presented as a way to enable more fine-grained scheduling and to better exploit opportunistic compute availability.
  - When challenged on novelty, the answer was that the general technique exists in graphics-type contexts, but applying it in this radio-simulation setting may still be valuable even if the underlying concept is not wholly new.

## Critique of the Current Digital Twin Direction

- The strongest feedback was that **preemptibility** should be treated as a first-order design requirement, not as an afterthought.
  - The digital twin was described as an elastic or background-style workload.
  - Because it is not inherently the same kind of hard-deadline workload as real-time inference or the RAN itself, it should be able to pause, shrink, or park itself when spare compute disappears.
- The conversation then focused on how that parking/resume behavior should work in practice.
  - One current design instinct was to preserve state in memory rather than performing a classic heavy checkpoint to disk.
  - The motivation was that disk-based save operations also consume resources and might themselves interfere with urgent high-priority work.
  - GH200-class servers were invoked as part of the justification, on the grounds that they are heavily provisioned for memory and might therefore allow in-memory state parking.
- That approach was not rejected outright, but it was not accepted uncritically either.
  - The lead pushed hard on whether this was simply the easiest implementation path rather than the best design.
  - Concerns raised included memory pressure, resilience, restart overhead, and whether parking whole application state is too coarse-grained.
  - A more granular state-management approach was suggested as something worth considering, because not all state necessarily needs to be preserved or restored in the same way.
- Isolation was also examined.
  - Compute isolation was said to rely on operating-system control groups.
  - Memory isolation and the practical interaction between a resumed workload and the protected RAN workload were left much less clear.
- The meeting also exposed a clarity problem in the architecture itself.
  - The presented distributed diagram showed nodes containing gNodeBs, UEs, and RT workers.
  - The lead repeatedly asked how the actual digital-twin scenario maps onto those nodes in a conceptually clean way.
  - The explanation remained implementation-heavy and was not yet persuasive as a research abstraction.
  - This was treated as a warning sign that the design vocabulary and system picture still need simplification.

## Research Expectations Set by the Meeting

- A central message of the meeting was that the digital-twin work should not jump directly from one candidate architecture to implementation.
- The expected path is instead:
  - identify the design alternatives,
  - compare them qualitatively,
  - explain the pros and cons,
  - argue why the chosen design is the right hypothesis,
  - and only then invest heavily in implementation and evaluation.
- This was framed as the difference between being merely helpful on engineering tasks and actually owning a thesis-worthy research contribution.
- The lead explicitly warned against trying to “show progress” too quickly if that progress is not tied to a clear research argument.
- Another important correction was that evaluation methodology should not be the first question if the problem framing itself is still immature.
  - Before asking exactly what should be compared with a real testbed, the work first needs a firm answer to why the digital twin exists in this AI-RAN context and what properties it must preserve.
- The digital twin was described as having a specific role:
  - it should mimic the real network closely when conditions are matched,
  - but it also has flexibility unavailable to the real network, such as running in virtual time or using different scale assumptions,
  - which is precisely why it is useful for exploration and learning.
- The meeting therefore elevated the digital twin from “one more workload we can host” to “an important workload class that others are not clearly accounting for yet in AI-RAN.”

## Spotlight and Monitoring-System Discussion

- The second transcript segment shifted from the digital twin to the monitoring system and the Spotlight pipeline.
- The first part of that discussion clarified external context:
  - a workshop submission outcome was expected to be favorable,
  - but the workshop link that had been shared was meant as a landscape signal, not as an instruction to rush unfinished research,
  - and Dheeraj was explicitly told not to over-interpret the workshop as a hard pressure point.
- The conversation then returned to the technical problem of adapting Spotlight from its original single-cell context to a multi-cell campus deployment.
- Three broad options emerged from the discussion:
  - flatten all cell KPIs into one very wide dataset and train a model on that combined representation,
  - redesign the architecture so that the model becomes agnostic to the number of cells,
  - or keep a more local interpretation and treat each cell as a separate detection scope.
- The first option was considered overly specific to the current architecture and unlikely to scale cleanly.
- The second option was understood as potentially more elegant long-term, but too expensive in redesign effort for the immediate need.
- The recommended near-term direction was the third option:
  - treat each cell as its own central point of detection,
  - keep the existing pipeline logic as intact as possible,
  - run multiple single-cell detectors,
  - and infer a broader issue if several cells fire together.
- That recommendation was justified as a practical midpoint in the design space.
  - At one extreme, all telemetry could be centralized into a fully multivariate network-wide anomaly detector.
  - At the other extreme, each KPI source could be treated in a purely univariate and highly local fashion.
  - The per-cell detector view was presented as an acceptable middle ground that fits the current system and avoids unnecessary re-architecture.
- The meeting also clarified why this matters immediately.
  - Spotlight can become a concrete **application** on top of the monitoring system.
  - That makes it useful for demonstration to visitors.
  - It also makes it useful as a use-case section in the monitoring-system paper being assembled by Ujjwal.
- Beyond the near-term use case, Spotlight was also framed as a potential baseline for later work from others that may move toward more advanced unsupervised or frontier-pushing directions.

## Data, Validation, and Demonstration Guidance for Spotlight

- A practical constraint acknowledged in the meeting was that KPI properties can strongly affect model behavior.
  - Some KPIs may contain zeros or negative values that destabilize the current implementation.
  - That means the data-preparation and feature-alignment stage cannot be skipped or treated as trivial.
- The lead advised keeping the initial goal modest and operational:
  - align Spotlight with the KPIs that are already collected in Campus 5G,
  - train on normal data,
  - use held-out normal data for sanity checks,
  - and create synthetic anomalies to test whether the system fires when it should.
- The sanity-check requirement was important.
  - The model should not misfire on held-out normal data simply because of natural variability.
  - That means the validation stage needs both positive and negative evidence:
    - synthetic anomalies to verify sensitivity,
    - held-out normal samples to verify that false positives are not obviously broken.
- The conversation also pointed to a longer-term data opportunity through the Keysight emulator.
  - The emulator can help generate richer and more diverse data,
  - while still preserving continuity with the real stack because the higher-level system is real and the RU/UE side is what gets emulated.
- This created a useful medium-term path:
  - first make the app work in the real campus testbed in a limited single-cell sense,
  - then use the emulator to widen the data and broaden the baseline later.

## Administrative and Coordination Notes

- The meeting included a short set of concrete coordination items outside the main research debate.
- Dheeraj had a monitoring-system-related video already being revised based on Andrew’s feedback.
  - The direction was to finish the revision,
  - have it reviewed by Ujjwal and Andrew,
  - and circulate it again quickly.
- A logistics question came up around whether a display can be arranged on-site.
  - Ujjwal was treated as the likely person to coordinate that because he would already be present and would have the best chance of checking what the organizers allow.
- A support / recommendation-style letter for an asset or application was also discussed.
  - The lead said the main requirement was that the letter stay factual and make the benefit case clearly.
  - The expectation was that the signed version could be turned around the same night once the draft was shared.
- The overall tone of these exchanges reinforced a broader point from the technical discussion:
  - immediate coordination tasks should be handled cleanly,
  - but they should not distort the technical priorities or create artificial urgency around unfinished research ideas.

## Open Questions and Unresolved Issues

- For the digital twin:
  - what are the real design alternatives for making it preemptible and resource-adaptive?
  - when is in-memory parking the right answer, and when does it create hidden pressure or fragility?
  - how should state be represented so that pause / resume is cheap but not overly coarse?
  - how should the digital-twin scenario map cleanly onto the distributed execution nodes?
  - how should fidelity be chosen dynamically so that realism is preserved where necessary without making the twin too expensive to host?
- For the monitoring / Spotlight thread:
  - how much multi-cell interaction signal is truly needed for the initial useful version?
  - what KPI preprocessing is required to avoid avoidable model instability?
  - how should root-cause reporting be handled when anomalies may span multiple cells?
  - how much of the future multi-cell redesign should be postponed so that the immediate app still lands on time?

## Responsibilities and Ownership

- **Dheeraj**
  - Owns the digital-twin workstream being discussed in the first half of the meeting.
  - Was explicitly asked to step back from implementation-first instincts and instead compare design alternatives, justify the architecture, and treat that justification as part of the research contribution.
  - Is also the immediate implementer / integrator for the Spotlight use case in Campus 5G.
  - Was asked to revise the monitoring-system video, align with Ujjwal on the application / paper angle, and move the Spotlight integration toward a demonstrable state.

- **Ujjwal**
  - Is the main coordination point for the monitoring-system paper and for how Spotlight can appear inside it as an application or use case.
  - Was also treated as the likely coordination point for practical on-site display logistics.

- **Andrew**
  - Had already provided feedback on the monitoring-system video and was part of the requested short-cycle review path for the revised version.

- **Igor and the broader monitoring / anomaly-detection collaborators**
  - Were implicitly part of the broader monitoring and anomaly-detection context.
  - Their surrounding work was referenced as part of the wider trajectory into more advanced or less supervised directions.

## Next Steps

- Rework the digital-twin story around **design alternatives first**, not implementation first.
- Prepare a clearer explanation of:
  - what the digital twin is in this project,
  - why it is a co-located non-RAN workload worth studying,
  - what design options exist for resource adaptation and preemptibility,
  - and why the preferred design is better than the alternatives.
- Simplify the architecture description so that the mapping from digital-twin scenario to execution nodes is understandable at the research level, not just at the implementation level.
- Revisit the state-management / pause-resume design and examine downsides, not just benefits, of keeping parked state in memory.
- Keep the Spotlight near-term plan deliberately narrow:
  - use a single-cell interpretation,
  - fit it to Campus 5G,
  - train on normal data,
  - validate with held-out normal data,
  - and inject synthetic anomalies for testing.
- Coordinate with Ujjwal so that Spotlight becomes a concrete application example in the monitoring-system paper and a demonstrable app for visitors.
- Finalize the revised monitoring-system video after incorporating feedback and route it through the agreed review chain.
- Use richer emulator-driven data later, after the campus-facing version is stable enough to serve as a baseline.

# AI-RAN Meeting Summary, Meeting 3 (source date not captured in file)

## Overview

This short follow-up discussion focused narrowly on **KV-cache management under fluctuating memory availability**. The core issue was not whether spare memory can be used to hold KV cache for performance reasons, but how that cache should be released quickly and safely once the system needs the memory back. The conversation treated this as a real systems problem rather than something that can be delegated automatically to the platform without explicit policy.

## Main Technical Discussion

- The discussion started from the assumption that there may be enough spare memory to keep KV cache resident for performance reasons.
- That led immediately to the harder question: what happens when another workload or another layer suddenly needs that memory back while computation is still ongoing?
- A key clarification in the conversation was that the system may not simply and automatically clean up KV cache on behalf of the application.
  - If the cache must be released, somebody needs logic that explicitly frees or evicts it.
  - That means cache management cannot be hand-waved away as “the system will handle it.”
- At the same time, the participants noted that there are known strategies for evicting older KV-cache entries and maintaining a more controlled budget.
- The motivating systems intuition was:
  - when memory is abundant and unused, keeping KV cache resident can be beneficial,
  - but that benefit only holds if the system can react **very quickly** when the memory becomes needed elsewhere.
- The real design tension, therefore, is between:
  - performance from retaining KV cache,
  - and responsiveness when the platform must reclaim memory under pressure.

## Key Takeaways

- **KV cache should be treated as a budgeted resource, not as permanently free memory.**
- **Fast release matters as much as cache retention.** It is not enough to exploit spare memory if the system then reacts too slowly when the memory must be reclaimed.
- **Explicit policy is needed.** The conversation implies that some layer of software needs a deliberate mechanism for eviction, budgeting, or fast reclamation rather than assuming that the platform will invisibly solve it.
- **Old-cache eviction is a likely part of the answer.** Maintaining a bounded KV-cache budget and aging out less useful entries was mentioned as a plausible strategy.

## Open Questions and Unresolved Issues

- Which software layer should own the KV-cache release logic?
- How aggressive should eviction be when memory pressure begins to rise?
- How should the system balance retained KV cache for throughput / latency gains against the need to preserve headroom for higher-priority work?
- What is the right trigger for reclaiming cache:
  - explicit application policy,
  - platform-level pressure detection,
  - or a hybrid mechanism?

## Next Steps

- Investigate a concrete strategy for **fast KV-cache release / budgeting**.
- Look into mechanisms for evicting older KV-cache state while maintaining a predictable memory envelope.
- Clarify whether the desired behavior should live primarily in the application / runtime logic, in the system software, or in a layered combination of both.
- Evaluate how quickly cache can be reclaimed in practice once memory is required elsewhere.