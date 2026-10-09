# Generative-media methods and model research

Research cutoff: **2026-10-06**. Live web searches and primary-source checks were performed on that date. This is a design comparison, not a replication of the papers, a model leaderboard, or a claim of exhaustive internet coverage. No generation APIs, paid judges, or downloaded model weights were executed. Companion claim register: [media-sources.json](media-sources.json).

## Assessment of the brief

The brief's strongest choices are independent quality dimensions, blind human comparison, versioned rubrics and evaluators, explicit disagreement, hard failures that cannot disappear in averages, and a backend that operates on fixtures before expensive inference. These choices are compatible with established benchmark work. Its missing layer is **measurement validity conditioned on the intended use**: a score is a measurement from an instrument under a protocol, not an intrinsic fact about a clip.

Recommended architecture separates four questions:

1. **Intent compliance:** What did the requester mean to achieve, for whom, under what world assumptions and constraints?
2. **Observed media behavior:** Which requirements are visibly satisfied or violated, during which intervals, with what coverage?
3. **Instrument validity:** Can this particular human, detector, VLM, or panel reliably measure this property under this protocol?
4. **Decision utility:** Does the evidence justify shipping, repairing, regenerating, or requesting more evidence for this production context?

These are design inferences from the literature below. The ontology should preserve links among them without pretending that association establishes cause or that a model can read an artist's unexpressed intention.

## Baseline methods and what to retain

**VBench and VBench++.** VBench decomposes video evaluation into 16 dimensions, with tailored prompts and human alignment checks. VBench++ extends evaluation to image-to-video and trustworthiness. Retain the dimensional decomposition and category-specific validation. Treat dimension scores as different instruments; a score on one dimension is not a calibrated severity score on another. These papers support a benchmark adapter, not replacement of the lab's production rubric. [VBench](https://arxiv.org/abs/2311.17982), [VBench++](https://arxiv.org/abs/2411.13503).

**VBench-2.0.** Its five high-level areas—human fidelity, controllability, creativity, physics, and commonsense—extend beyond appearance. Keep explicit human/anatomical and causal/physical failure categories and targeted tests. The brief's physics and temporal-geometry separation is useful, but a physics judgement must reference a world assumption and observable event. Do not call benchmark compliance proof of a world simulator. [Paper](https://arxiv.org/abs/2503.21755), [official implementation](https://github.com/Vchitect/VBench/blob/master/VBench-2.0/README.md).

**EvalCrafter.** Uses 700 prompts, 17 objective metrics, and human-aligned weighting. It supports a multi-instrument view rather than one global metric. Its fitted weights are not universal preferences: a new professional audience, model family, or task may require recalibration. Preserve raw metrics and their versions; do not copy leaderboard coefficients as the lab's shipping policy. [Paper](https://arxiv.org/abs/2310.11440).

**T2V-CompBench.** Evaluates seven compositional categories using MLLM, detection, and tracking methods. This directly motivates typed requirements for who performs an action, attribute ownership, spatial relations, count, interaction, and temporal change. A bag of object tags cannot represent these requirements. An evaluator should distinguish a correct object appearing from the correct subject performing the intended action. [Paper](https://arxiv.org/abs/2407.14505).

**VideoScore.** Learns multi-aspect assessment from VideoFeedback, a human-annotated set of 37.6K synthesized videos. This is a useful trained-judge baseline; reported correlation applies to the paper's data and protocol. Its training distribution is older than October 2026 generation models, so local calibration and family-held-out tests are prerequisites. The model's confidence is not automatically calibrated evidence. [Paper](https://arxiv.org/abs/2406.15252), [model card](https://huggingface.co/TIGER-Lab/VideoScore-v1.1).

**FVD and static similarity.** FVD compares distributions and documented content bias can underweight temporal degradation. It should never decide whether one clip satisfies a prompt. CLIP-like alignment can also fail on compositional role reversals. Keep such metrics as diagnostic signals with explicit scope, not individual-shot truth. [FVD content-bias study](https://openaccess.thecvf.com/content/CVPR2024/papers/Ge_On_the_Content_Bias_in_Frechet_Video_Distance_CVPR_2024_paper.pdf), [VQAScore study](https://arxiv.org/abs/2404.01291).

**Image evaluation.** GenEval offers object-focused alignment; GenAI-Bench examines compositional text-to-visual generation. Their value is controlled requirement testing, not an overall aesthetic score. Record dataset authors and paper IDs: the Lin et al. GenAI-Bench and the TIGER-Lab GenAI-Arena-derived dataset share a name but are not interchangeable. [GenEval](https://arxiv.org/abs/2310.11513), [Lin et al. GenAI-Bench](https://arxiv.org/abs/2406.13743), [TIGER-Lab dataset](https://huggingface.co/datasets/TIGER-Lab/GenAI-Bench).

## Freshness sweep: changes beyond the initial benchmark set

**GenEval 2, submitted 2025-12-18**, documents benchmark drift and introduces more compositional coverage and Soft-TIFA. Its message for sustainability is to audit the evaluator as generators evolve. Keep a frozen regression suite for longitudinal comparability alongside a separately versioned rolling challenge set. A new challenge set must not silently rewrite historical scores. [Paper](https://arxiv.org/abs/2512.16853).

**DynamicEval, submitted 2025-10-08**, explicitly examines dynamic camera motion, foreground/background consistency, and occlusion-related weaknesses in earlier metrics. This supports the brief's camera-versus-world distinction. Record the motion frame of reference and coverage of occlusion/disocclusion intervals. An optical-flow anomaly alone does not establish broken physics. [Paper](https://arxiv.org/abs/2510.07441).

**T2VPhysBench and PhyWorldBench (2025)** introduce first-principles and anti-physics/counterfactual testing. Use paired intent conditions: realistic gravity, declared fantasy gravity, and an ambiguous request. A surreal shot can satisfy its prompt while violating terrestrial mechanics. Store both observations instead of forcing one scalar judgement. [T2VPhysBench](https://arxiv.org/abs/2505.00337), [PhyWorldBench](https://arxiv.org/abs/2507.13428).

**RAVEN-Eval, submitted 2026-08-10**, uses task-specific rubrics, pairwise judging, and anchor-based insertion of new models. It is particularly relevant to efficient comparison. The full paper acknowledges sparse-frame limitations for motion and incomplete human annotation coverage. Use pairwise comparison after minimum requirement checks; route uncertain temporal claims to denser evidence. Order-reversal inconsistency should remain a separate measurement problem rather than becoming a genuine tie. [Paper and limitations](https://arxiv.org/html/2608.09111v1).

**VGA-BenchV2, submitted 2026-08-26**, separates aesthetic and generation quality with 52 subdimensions and specialized evaluators. This reinforces preserving craft versus correctness. Do not import dozens of dimensions before demonstrating that raters can distinguish them: maintain a taxonomy and activate a small task-relevant subset. [Paper](https://arxiv.org/abs/2608.25452).

**VGI-Bench, August 2026**, evaluates visual intelligence in generated outputs. **KIVI-Bench, revised 2026-09-28**, evaluates factuality and helpfulness for explanatory/procedural video. These motivate intended outcome and domain-knowledge requirements beyond prompt-word matching. They do not justify assigning medical or scientific correctness using general visual preference alone. [VGI-Bench](https://arxiv.org/abs/2608.19583), [KIVI](https://arxiv.org/abs/2606.01285).

**VTR-Bench, submitted 2026-10-01**, separates visual text fidelity from scene/motion requirements and explores an agentic keyframe workflow. The current brief marks typography optional; promote it to an available requirement type now, activating it when a prompt requires readable text. OCR accuracy alone cannot validate that the text remains attached to the right carrier through time. This is a fresh preprint, not a mature industry standard or independently replicated result. [Paper](https://arxiv.org/abs/2610.01499).

**VABench (2025 preprint; CVPR 2026)** covers synchronous audio-video evaluation, including alignment and synchronization. Audio can stay outside the Phase 4 executable implementation, but the evidence and capability contracts should represent audio, speech, synchronization, and missing audio explicitly. A video-only evaluator must abstain from these dimensions. [Paper](https://arxiv.org/abs/2512.09299), [CVPR proceedings](https://openaccess.thecvf.com/content/CVPR2026/papers/Hua_VABench_A_Comprehensive_Benchmark_for_Audio-Video_Generation_CVPR_2026_paper.pdf).

## Model candidate inventory at the cutoff

These are **documented integration candidates, not quality recommendations**. Availability is evidence-specific: product access, API documentation, open weights, preview, and announced future capability are different states. No provider access was tested; licenses, regional access, prices, and account entitlements require checking before execution.

- **Google Veo 3.1:** current official Veo page documents video, reference controls, and audio. Its published comparison charts state October 2025, so they do not establish an October 2026 ranking. [Official page](https://deepmind.google/models/veo/).
- **Google Gemini Omni Flash (`gemini-omni-1.1-flash`):** the API changelog records GA on 2026-08-27, including extension and interpolation. Keep it distinct from Veo rather than treating Google's generation portfolio as one model. [Release notes](https://ai.google.dev/gemini-api/docs/changelog).
- **Runway Gen-4.5:** current help documents text-to-video and image-to-video usage. Evaluate camera direction and ordered actions with task-specific prompts; do not infer API entitlement or native audio from generic marketing copy. [Official help](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5).
- **Seedance 2.0:** official launch is dated 2026-02-12, with text/image/audio/video reference inputs. This establishes a release announcement and documented capabilities; account/region/API access is a separate check. [Official launch](https://seed.bytedance.com/en/blog/seedance-2-0-official-launch).
- **Kling 4.0 / 4.0 Flash:** the 2026-09-30 official post describes early access and wider October rollout. It separately marks HDR and longer extension as coming soon. Treat it as early-access evidence, not verified universal availability. [Official post](https://kling.ai/blog/kling40-kling-visual-realism-creative-control-introducing-storytelling?tab=all).
- **Wan 3.0 (`wan3.0-video`):** the live Alibaba Cloud API guide documents the endpoint and migration from 2.7. This is distinct from the open Wan2.2 checkpoints. A GitHub announcement repository is not proof that 3.0 weights were released. [API guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-guide/), [Wan2.2 repository](https://github.com/Wan-Video/Wan2.2), [Wan3.0 repository](https://github.com/AlibabaCloud-Official/Wan3.0).
- **LTX-2.5:** the official code repository recommends it and links published component weights; the model card identifies gated access and a community license. API and local pipelines have different documented constraints. Retain older LTX-2.3 as a reproducibility baseline, not the latest candidate. [Repository](https://github.com/Lightricks/LTX-2), [model card](https://huggingface.co/Lightricks/LTX-2.5), [API guide](https://docs.ltx.io/models/ltx-2-5).
- **OpenAI Sora 2:** historical/import-only candidate. Official API deprecations list shutdown of Sora2 and Videos API on **2026-09-24**. Do not build a new active provider around it. [Official OpenAI documentation](https://developers.openai.com/api/docs/deprecations).
- **OpenAI GPT Image 2.5 Sunburst / Flare:** current API reference lists aliases and dated `2026-09-08` snapshots. A snapshot date is not automatically the product announcement date. Pin the exact identifier for later image evaluation. [API reference](https://developers.openai.com/api/reference/resources/images/methods/generate).
- **Google Nano Banana 2.1:** the release notes dated **2026-10-06** list `gemini-nano-banana-2.1` as GA; predecessor shutdown is announced for October 29. Today's release belongs in the candidate register but needs a local qualification run before adoption. [Release notes](https://ai.google.dev/gemini-api/docs/changelog).
- **Black Forest Labs FLUX.2:** official documentation distinguishes max/pro/flex/klein/dev and API versus local usage. Version, quantization, fine-tunes, and license all belong in lineage. Do not claim every variant has the same license or identical capabilities. [Vendor overview](https://help.bfl.ai/articles/4292391522-what-is-flux-2), [official inference repository](https://github.com/black-forest-labs/flux2).

For multimodal judging, shortlist several independent instruments rather than appointing one universal judge:

- **Gemini 3.8 Flash** documents text/image/video/audio input and structured outputs, with GA recorded 2026-09-02. It is a native-media candidate, but native video input alone does not prove adequate frame coverage or temporal reasoning. [Model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
- **Qwen3.8-27B** is an open-weight native vision-language candidate that documents image/video understanding; the official repository dates this release to 2026-08-14. Record exact weights, preprocessing, quantization, and runtime. Hardware feasibility remains untested. [Model card](https://huggingface.co/Qwen/Qwen3.8-27B), [release history](https://github.com/QwenLM/Qwen3.8).
- **GPT-6 Astra** documents image input, structured outputs, and no native audio/video modality. It can be considered for sampled-frame reasoning, never silently represented as having viewed a full clip. [Official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-6-astra).
- **Claude Opus 5.5 / Sonnet 5.5 / Fable 5.1** appear in the current official model catalog, which specifies text/image inputs. Treat them as image/evidence judges unless a separate supported video interface is verified. Their relative media-judge quality remains unknown. [Official catalog](https://platform.claude.com/docs/en/models/overview).
- **VideoScore and specialized detectors** remain useful controls. Newer generalist models do not eliminate the need for detectors, trackers, OCR, or blinded humans. Ensemble diversity must be measured through residual errors; three prompts using the same base model are not three independent witnesses.

## Concrete additions above the benchmark layer

The following are proposed lab policies, not claims that the cited papers already implement the whole system.

**Requirement and intent records.** Add a requester/stakeholder, intended audience, desired outcome, priority, world assumptions, rationale, observable acceptance criterion, exclusions, provenance, and approval state. Relations need direction, roles, scope, and time: `subject PERFORMS action`, `action TARGETS object`, `requirement SERVES intent`, `evidence SUPPORTS requirement`, `test DISCRIMINATES hypothesis`, and `intervention PRESERVES/COMPROMISES intent`. Mark inferred intent as proposed until validated.

**Observation versus interpretation.** Store a timecoded observation separately from its causal interpretation. "The foot translates while planted" is an observation; "bad locomotion model" is a hypothesis. A stabilizing-camera test can change confidence without pretending a semantic explanation is a demonstrated mechanism.

**Applicability and observability.** Every assessment needs status (`assessed`, `not_applicable`, `insufficient_evidence`, `invalid_instrument`) independent of the ordinal 0–4 score. An image cannot pass temporal consistency; a one-frame judge cannot clear a collision. Unknown is not zero and not a pass. Hard failures apply only to valid, applicable requirements under a versioned decision policy.

**Evidence coverage.** Persist original media checksum, decoded derivative hashes, selected frame timestamps, extraction/sampling version, total duration, audio availability, crop/resize/color handling, and known blind spots. Adaptive tools should log which intervals they inspected. A dense temporal instrument may escalate an issue missed by sparse keyframes.

**Validity before automatic acceptance.** Validate judges against held-out human evidence by dimension and slice. Include A/B reversal, rubric paraphrases, identity blinding, irrelevant watermark, temporal reorder, frozen-frame substitution, prompt contradiction, intentional stylization, and missing-evidence controls. Calibration and false-negative rates for catastrophic failures matter more than overall correlation. Thresholds are task policies requiring empirical calibration, not universal constants from a paper.

**Efficient human handoff.** Begin with deterministic checks and reusable extraction, then cheap qualified specialists, then expensive judges only where expected information could change the decision. Send humans a bounded evidence packet: unresolved requirement, disputed timestamps, competing explanations, proposed discriminating test, uncertainty, and deadline. Preserve a random audit stream as well as uncertainty sampling, because confident errors are invisible to uncertainty-only routing.

**Production utility.** Add accepted-shot rate, human review minutes, adjudication rate, false acceptance of critical defects, cost per accepted shot, regeneration count, and measured post-production time. A VFX recommendation should expose required repair, expected preserved intent, confidence, and evidence. Calibrate repair estimates against actual artist work before claiming automated salvage expertise.

**Sustainable versioning.** Keep frozen comparisons, rolling challenges, evaluator qualification, and provider capability discovery separately versioned. Store prompt before/after rewrite, seed where supported, reference assets, generation parameters, duration/resolution/audio settings, and postprocessing. Public cases can cite prior models without depending on their continued API availability. Refresh discovery when preparing a new evaluation, while production adopts a candidate only after qualification; this document does not create a scheduled task.

## Fact-check sweep and corrections

1. Opened primary arXiv pages to verify dates. RAVEN's submission is August **10**, despite an aggregator showing August 11. VTR's October 1 submission is within the requested cutoff. KIVI has a September 28 revision. Future October papers are not implied covered.
2. Read RAVEN's full-text limitations: incomplete human annotation and sparse-frame temporal limitations prevent an unrestricted automatic-approval claim.
3. Opened current vendor documentation after initial search snippets. Corrected LTX-2.3 to LTX-2.5 and Wan2.6 to documented Wan3.0 for current candidate discovery. Historical versions remain valuable baselines.
4. Read Kling's body, not only its title: recorded early access and coming-soon features separately.
5. Opened official OpenAI deprecations: Sora2 is not an active October 2026 API candidate. Read modality tables: GPT-6 Astra is not a native video model.
6. Checked model catalog against dated Google release notes: Nano Banana2.1 appears on October 6; Gemini3.8 Flash has September2 GA. The catalog's generic Preview grouping and Omni's dated GA entry are not treated as stronger than the model-specific release event.
7. Excluded unsupported universal rankings, dollar-cost estimates, exact licensing interpretations, and claims of reproduction. Vendor-reported quality gains and paper correlations are source claims, not locally verified findings.
8. Noted a count inconsistency in PhyWorldBench's abstract (total models versus listed group subtotals); no model-count claim is used here. Use the final paper tables if that count becomes operationally relevant.

## Search log and coverage limitations

The sequence was discovery → architecture comparison → targeted freshness search → primary-source reopening/fact check. Representative query batches (all 2026-10-06):

- `VBench 2.0 intrinsic faithfulness video generation benchmark arxiv`; `EvalCrafter T2V CompBench VideoScore video generation evaluation arxiv`.
- `site.arxiv.org video generation evaluation benchmark 2026 September`; `site.arxiv.org VideoScore video generation human feedback 2024`; `site.arxiv.org video generation physics evaluation PhysBench PhyGenBench 2025 2026`.
- `site.arxiv.org/abs/ "2026" "video generation" "benchmark"`; `site.arxiv.org/abs/ "2026" "video generation" "evaluation" "September"`; `site.arxiv.org "FVD" "content bias"`.
- `site.arxiv.org/abs GenEval benchmark image generation 2023`; `site.arxiv.org/abs GenAI-Bench human preferences compositional image video 2024`; `site.arxiv.org/abs VQAScore visual question answering models image text alignment`.
- Official-domain searches for Veo, Runway Gen-4.5, Seedance2, Kling3/3.5 followed by Kling4; Wan2.2/2.5/2.6 followed by Wan3; LTX2.3 followed by LTX2.5; FLUX2.
- Official OpenAI documentation searches for `Sora 2 deprecation`, `models image generation GPT image`, followed by model-catalog, API-reference, deprecation, and modality-page checks.
- Official searches for Qwen3/VL/2026, Gemini models and release notes, Claude model overview and September2026 releases; followed redirects and opened current model cards.
- Fresh-source followups opened RAVEN-Eval, VTR-Bench, VGA-BenchV2, KIVI, VGI-Bench, GenEval2, and DynamicEval directly at arXiv, with full-text reads for RAVEN, VTR, and GenEval2.

This is a broad, relevance-filtered research pass, not a systematic review with exhaustive database recall. New preprints may be unindexed. Many commercial details remain dynamically rendered or account-dependent. Coverage concentrates on generation quality, judges, and intent/composition; standards, human-study methodology, agent orchestration, and firsthand practitioner methods are covered by the companion research work. No model was crowned best. The sound immediate testing target is the lab's contracts, invariants, and adversarial fixtures; real-world validity requires actual media and independent calibrated raters in later phases.
