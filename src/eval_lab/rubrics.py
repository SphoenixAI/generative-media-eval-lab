from datetime import datetime, timezone
from .domain import Dimension as D, EvaluationDimension, Rubric


def initial_rubric() -> Rubric:
    """Provisional anchors; human calibration is still required. 0 -> 4."""
    rows = (
        (D.PROMPT, "instruction", "Requested instructions are fulfilled", (
            "Central requested action or subject absent or reversed", "A major explicit requirement fails", "A secondary explicit requirement materially fails", "Small deviation preserving the requested meaning", "All applicable explicit requirements satisfied"), 1, None,
            "Judge against declared intent, not inferred artist preferences."),
        (D.SUBJECT, "instruction", "Subject identity and intended state persist", (
            "Identity or body topology fundamentally mutates", "Repeated identity loss obscures the subject", "Visible identity drift affects interpretation", "Brief minor detail drift with identity intact", "Identity stable through observed coverage"), 0, None,
            "Intentional transformations are evaluated against the intended state sequence."),
        (D.SEMANTIC, "instruction", "Intended meaning persists", (
            "Scene meaning contradicts intended event", "Meaning changes for most of the clip", "Meaning drifts during a material interval", "Small semantic ambiguity without narrative loss", "Meaning remains consistent with intent"), None, None,
            "Meaning is distinct from exact instruction coverage."),
        (D.TEMPORAL, "temporal_physical", "Scene state is coherent over time", (
            "Scene state repeatedly resets or contradicts itself", "Major state discontinuity breaks the event", "Noticeable continuity failure affects interpretation", "Brief minor discontinuity", "State evolves consistently across observed time"), None, None,
            "State continuity is broader than geometry; do not double-count in an average."),
        (D.GEOMETRY, "temporal_physical", "Spatial relationships persist plausibly", (
            "Topology or scene structure becomes impossible", "Major spatial deformation disrupts the shot", "Local geometry deformation affects interpretation", "Small transient deformation outside primary action", "Geometry coherent across relevant views and occlusion"), 0, 0,
            "Stylized impossible worlds can declare this criterion not applicable."),
        (D.MOTION, "temporal_physical", "Movement fits the intended physical world", (
            "Central action is mechanically impossible", "Repeated impossible contacts or accelerations", "Local contact or motion failure affects action", "Small incidental motion anomaly", "Motion fits declared physics and action"), None, None,
            "Camera-relative movement alone cannot establish world-motion failure."),
        (D.OCCLUSION, "temporal_physical", "Visibility ordering is coherent", (
            "Central foreground and background relationships contradict", "Repeated impossible occlusions", "A material local occlusion error", "Small peripheral occlusion error", "Visibility ordering coherent across observed transitions"), None, None,
            "Need transition evidence, not an isolated frame."),
        (D.LIGHTING, "temporal_physical", "Lighting evolves consistently", (
            "Lighting and shadows fundamentally contradict the scene", "Repeated major lighting discontinuities", "A visible lighting jump harms shot continuity", "Minor local lighting fluctuation", "Lighting follows declared scene and style"), None, None,
            "Intentional lighting cuts must be declared before grading."),
        (D.CAMERA, "craft", "Camera behavior communicates the intended shot", (
            "Camera grammar defeats the intended shot", "Severe unintended camera or lens discontinuity", "Movement or framing materially obscures action", "Minor drift preserves the intended shot", "Camera and lens behavior fit the declared shot"), None, None,
            "Coherent world with poor camera grammar is not automatically physics failure."),
        (D.COMPOSITION, "craft", "Visual hierarchy serves the intended communication", (
            "Required subject/action cannot be read", "Hierarchy repeatedly obscures the intended focus", "Competing elements materially weaken focus", "Small distraction with clear subject hierarchy", "Composition clearly supports declared visual intent"), None, None,
            "This is contextual craft judgment; preference differences may be irreducible."),
        (D.ARTIFACT, "craft", "Synthesis artifacts do not disrupt the output", (
            "Corruption makes the primary content unusable", "Large recurring warps or flicker dominate", "Visible artifacts materially distract", "Small local artifact away from critical action", "No material synthesis artifacts in observed coverage"), None, None,
            "Intentional textures or effects are not defects merely because unusual."),
        (D.AESTHETIC, "craft", "Output is compelling for the declared audience and style", (
            "Output defeats declared aesthetic direction", "Strong mismatch with declared direction", "Material mismatch weakens intended effect", "Minor aesthetic weakness", "Convincing execution of declared aesthetic intent"), None, None,
            "Preference is not universal correctness and cannot overrule hard failures."),
        (D.EDITABILITY, "craft", "Repair preserves the required shot within its budget", (
            "No known repair preserves essential shot requirements", "Repair likely needs major reconstruction", "Repair needs substantial tracking or cleanup", "Small local cleanup likely sufficient", "No material repair required"), None, None,
            "Provisional triage only; costs require an actual production artist and brief."),
    )
    return Rubric(id="core-rubric", version="0.1.0", created_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        dimensions=tuple(EvaluationDimension(dimension=d, family=f, description=desc,
            anchors=a, hard_fail_at_or_below=fail, regenerate_at_or_below=regen, boundary_note=b)
            for d,f,desc,a,fail,regen,b in rows),
        rationale="Provisional small anchored ordinal scale. Intent determines applicability; critical failures veto. Validate anchors with humans before release.")
