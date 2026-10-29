from situations_a import L0, G, H, E, ST, R, RULES, GAP

DIZZY = {
 "id": "dizziness", "title": "Acute dizziness or vertigo", "setting": "Emergency department", "population": "Adults, symptoms under 2 weeks",
 "priority": "Common ED complaint with a 2023 GRADE guideline.", "priority_source": None,
 "lead_guidelines": ["grace3", "grace3_pdf"], "status": "partial",
 "layer0": [
  L0("Timing and triggers", "Continuous for more than 24 hours (acute vestibular syndrome), triggered by position, or spontaneous episodes.", "grace3_pdf"),
  L0("Exam", "Nystagmus, HINTS (head impulse, nystagmus, test of skew), gait, Dix-Hallpike when positional.", "grace3")],
 "gate": [
  G(True, "Continuous dizziness (acute vestibular syndrome)", "Stroke must be excluded with HINTS by a trained examiner, then MRI if central or equivocal.", "grace3_pdf"),
  G(False, "Positional (triggered) episodes", "Dix-Hallpike for posterior canal BPPV; no CT and no routine MRI.", "grace3")],
 "gate_note": "Untrained clinicians apply and interpret HINTS inaccurately; GRACE-3 recommends training.", "gate_note_source": "grace3",
 "hypotheses": [
  H("stroke", "Posterior circulation stroke", "Stroke", "must_not_miss", "Continuous dizziness with central signs", "partial", "grace3_pdf"),
  H("bppv", "Posterior canal BPPV", "BPPV", "other", "Brief, positional episodes", "sourced", "grace3"),
  H("periph", "Peripheral vestibular syndrome (e.g. vestibular neuritis)", "Peripheral", "other", "Continuous, peripheral HINTS", "partial", "jfp_dizzy"),
  H("nonvest", "Non-vestibular cause (cardiac, orthostatic)", "Non-vestibular", "other", "See syncope", "stub", None)],
 "steps": [
  ST("Classify by timing and triggers", "First", "Decides which bedside test applies.", {
   "bppv": E("steer", "Triggered positional episodes.", "grace3"),
   "stroke": E("steer", "Continuous symptoms over 24 hours.", "grace3_pdf"),
   "periph": E("steer", "Continuous symptoms over 24 hours.", "grace3_pdf")}),
  ST("Dix-Hallpike test", "Positional episodes", "Diagnoses posterior canal BPPV.", {
   "bppv": E("conf", "Positive test diagnoses posterior canal BPPV; treat with Epley maneuver.", "grace3")}),
  ST("HINTS exam by a trained clinician", "Continuous dizziness", "Separates central from peripheral patterns.", {
   "stroke": E("rule", "A peripheral HINTS pattern helps rule out stroke, but only when performed by trained clinicians.", "jfp_dizzy"),
   "periph": E("conf", "Peripheral pattern supports a peripheral cause.", "jfp_dizzy")}),
  ST("MRI", "Central or equivocal HINTS", "Confirmatory test.", {
   "stroke": E("conf", "MRI confirms; in the first 48 hours it misses about 1 in 5 strokes presenting as dizziness.", "sgem_grace3")}, "grace3_pdf")],
 "rules": {
  "stroke": RULES("GRACE-3 (2023).",
   [R("Peripheral HINTS pattern in a patient with true acute vestibular syndrome, examined by a trained clinician.", "jfp_dizzy")],
   [R("HINTS done by untrained clinicians or in the wrong patients.", "grace3"),
    R("An early negative MRI alone: about 80% sensitive in the first 48 hours.", "sgem_grace3"),
    R("CT for positional dizziness.", "grace3")]),
  "bppv": RULES("GRACE-3 (2023).", [], [], "Confirmed rather than eliminated; positive Dix-Hallpike."),
  "periph": RULES("Partly sourced.", [], [], "Supported by a peripheral HINTS pattern."),
  "nonvest": RULES("Not yet researched.", [], [], "See the syncope situation.")},
 "gaps": [GAP("Training", "HINTS accuracy depends on examiner training, which most emergency physicians lack.", "grace3")]
}

FOCAL = {
 "id": "focal_deficit", "title": "Acute focal neurologic deficit (suspected stroke)", "setting": "Prehospital and emergency department", "population": "Adults (the 2026 guideline also adds pediatric guidance, not encoded here)",
 "priority": "Time-critical presentation with a 2026 guideline.", "priority_source": None,
 "lead_guidelines": ["aha_stroke_2026_gc", "aha_stroke_2026_pdf"], "status": "partial",
 "layer0": [
  L0("Complaint", "Sudden weakness, numbness, speech or vision loss.", None),
  L0("Timing", "Time last known well decides treatment eligibility.", "aha_stroke_2026"),
  L0("Bedside glucose", "Checked before thrombolysis; severe hypoglycemia or hyperglycemia can mimic stroke.", "aha_stroke_2026_gc")],
 "gate": [
  G(True, "Within a treatment window", "Stroke pathway immediately; brain imaging within 25 minutes; other tests must not delay reperfusion.", "medscape_stroke_2026"),
  G(False, "Outside known windows", "Still image urgently; the 2026 guideline widens some windows with perfusion imaging.", "pn_stroke_2026")],
 "gate_note": "Verified against the 2026 AHA/ASA guideline, which replaced the 2018 guideline and 2019 update.", "gate_note_source": "aha_stroke_2026",
 "hypotheses": [
  H("ais", "Acute ischemic stroke", "Ischemic stroke", "must_not_miss", "Sudden focal deficit", "partial", None),
  H("ich", "Intracranial hemorrhage", "Hemorrhage", "must_not_miss", "Sudden focal deficit", "sourced", None),
  H("hypo", "Hypoglycemia or severe hyperglycemia (stroke mimic)", "Glucose mimic", "must_not_miss", "Abnormal bedside glucose", "sourced", "aha_stroke_2026_gc"),
  H("mimic", "Other stroke mimics", "Other mimic", "other", "Not sourced", "stub", None)],
 "steps": [
  ST("Bedside glucose", "Before thrombolysis", "Detects and urgently corrects severe hypoglycemia or hyperglycemia.", {
   "hypo": E("rule", "Normal glucose, or a disabling deficit that persists after correction, means glucose does not explain the deficit.", "medscape_stroke_2026")}, "aha_stroke_2026_gc"),
  ST("Brain imaging: noncontrast CT or MRI", "Within 25 minutes of arrival", "Assesses ischemic burden and excludes hemorrhage before any reperfusion treatment (class 1, level A).", {
   "ich": E("rule", "Imaging without hemorrhage excludes intracranial hemorrhage before reperfusion.", "aha_stroke_2026_gc"),
   "ais": E("blind", "Mild to moderate early ischemic change neither precludes nor delays thrombolysis.", "medscape_stroke_2026")}, "aha_stroke_2026_gc"),
  ST("ECG and troponin", "Baseline", "Recommended, but must not delay treatment.", {
   "ais": E("steer", "Baseline ECG and troponin must not delay IV thrombolysis or thrombectomy.", "emdocs_stroke_2026")}),
  ST("Vascular and perfusion imaging", "Suspected large vessel occlusion within 24 hours; extended windows", "CT/CTA or MRI/MRA as fast as possible for thrombectomy selection.", {
   "ais": E("conf", "Perfusion imaging can select some unknown-onset patients for thrombolysis up to 9 hours.", "pn_stroke_2026")}, "emdocs_stroke_2026")],
 "rules": {
  "hypo": RULES("2026 AHA/ASA guideline.",
   [R("Normal bedside glucose.", "aha_stroke_2026_gc"),
    R("A disabling deficit persisting after glucose correction; thrombolysis is still recommended then.", "medscape_stroke_2026")], []),
  "ich": RULES("2026 AHA/ASA guideline, class 1, level A.", [R("Noncontrast CT or MRI without hemorrhage.", "aha_stroke_2026_gc")], []),
  "ais": RULES("2026 AHA/ASA guideline.", [], [R("Delaying treatment for ECG, troponin or advanced imaging.", "emdocs_stroke_2026"),
     R("Mild early ischemic change on CT as a reason to withhold thrombolysis.", "medscape_stroke_2026")], "Stroke is confirmed or treated, not eliminated, in this route."),
  "mimic": RULES("Not yet researched.", [], [], "Seizure, migraine and other mimics not sourced.")},
 "gaps": [GAP("Pediatric stroke", "The 2026 guideline adds pediatric recommendations, not encoded here.", "aha_stroke_2026"),
          GAP("Other mimics", "Mimics other than glucose disorders are not sourced.", None)]
}

LBP = {
 "id": "low_back_pain", "title": "Acute low back pain", "setting": "Primary care or ED", "population": "Adults",
 "priority": "Leading cause of disability under age 45; imaging overuse is a known problem.", "priority_source": "ajnr_lbp",
 "lead_guidelines": ["acr_lbp"], "status": "partial",
 "layer0": [
  L0("Duration", "Acute means 6 weeks or less.", "applied_rad_lbp"),
  L0("Red flags", "New urinary retention or overflow incontinence, loss of anal tone or fecal incontinence, saddle anesthesia, progressive leg weakness; also cancer history, infection, fracture risk.", "lbp_imaging")],
 "gate": [
  G(True, "Cauda equina features or severe or progressive deficit", "MRI urgently.", "acr_lbp"),
  G(False, "No red flags", "No imaging for uncomplicated pain under 6 weeks.", "applied_rad_lbp")],
 "gate_note": "Most uncomplicated acute low back pain needs no imaging.", "gate_note_source": "acr_lbp",
 "hypotheses": [
  H("ces", "Cauda equina syndrome", "Cauda equina", "must_not_miss", "Retention, saddle anesthesia", "partial", "lbp_imaging"),
  H("malig", "Spinal malignancy", "Malignancy", "must_not_miss", "Cancer history", "partial", "acr_lbp"),
  H("infx", "Spinal infection", "Infection", "must_not_miss", "Infection red flags", "partial", "acr_lbp"),
  H("fx", "Vertebral fracture", "Fracture", "must_not_miss", "Fracture red flags", "partial", "acr_lbp"),
  H("mech", "Uncomplicated mechanical back pain", "Mechanical", "other", "No red flags", "partial", "applied_rad_lbp")],
 "steps": [
  ST("Red-flag history and exam", "First visit", "The cornerstone of initial assessment.", {
   "ces": E("steer", "Bladder, bowel or saddle symptoms, or progressive weakness.", "lbp_imaging"),
   "malig": E("steer", "Cancer history raises suspicion.", "acr_lbp"),
   "infx": E("steer", "Infection red flags raise suspicion.", "acr_lbp"),
   "fx": E("steer", "Fracture red flags raise suspicion.", "acr_lbp"),
   "mech": E("steer", "No red flags makes uncomplicated pain likely.", "acr_lbp")}),
  ST("No imaging if no red flags", "Under 6 weeks", "All imaging is rated usually not appropriate.", {
   "mech": E("steer", "Half of patients recover in 2 weeks and 90% by 3 months.", "applied_rad_lbp")}),
  ST("MRI", "Red flags, or no improvement after 6 weeks", "Modality of choice for most patients who need imaging.", {
   "ces": E("conf", "MRI evaluates the cauda equina better than CT.", "applied_rad_lbp"),
   "malig": E("conf", "MRI is preferred when malignancy is suspected.", "lbp_imaging"),
   "infx": E("conf", "MRI is the modality of choice for most patients who need imaging.", "lbp_imaging")})],
 "rules": {
  "ces": RULES("ACR criteria and review.", [], [R("Imaging every patient; it does not improve outcomes in uncomplicated pain.", "applied_rad_lbp")], "No red flags means it is not pursued; MRI decides when flags are present."),
  "malig": RULES("ACR criteria and review.", [], [R("Malignancy red flags as proven; most lack empirical support.", "lbp_imaging")], "No exclusion rule beyond absent red flags."),
  "infx": RULES("Partly sourced.", [], [], "No exclusion rule beyond absent red flags."),
  "fx": RULES("Partly sourced.", [], [], "No exclusion rule beyond absent red flags."),
  "mech": RULES("Diagnosis of exclusion.", [], [], "What remains when red flags are absent.")},
 "gaps": [GAP("Red-flag evidence", "Many red flags lack empirical support; validated thresholds are missing.", "lbp_imaging")]
}

FLANK = {
 "id": "flank_pain", "title": "Acute flank pain (suspected stone)", "setting": "Emergency department", "population": "Adults, including pregnancy",
 "priority": "Has a dedicated ACR topic with four variants.", "priority_source": "acr_flank_narr",
 "lead_guidelines": ["acr_flank"], "status": "partial",
 "layer0": [
  L0("Complaint", "Sudden, colicky flank pain, often with blood in the urine.", "acr_flank_old"),
  L0("History", "Known stones, pregnancy, signs of infection.", "acr_flank_narr")],
 "gate": [
  G(True, "Signs of infection", "Covered by the separate ACR acute pyelonephritis topic.", "acr_flank_narr"),
  G(False, "No infection signs", "Image by patient group.", "acr_flank")],
 "gate_note": "Pregnancy changes the first test.", "gate_note_source": "acr_flank",
 "hypotheses": [
  H("stone", "Ureteral stone", "Stone", "other", "Colicky pain, hematuria", "sourced", "acr_flank_old"),
  H("pyelo", "Pyelonephritis or infected obstruction", "Infection", "must_not_miss", "Fever, infection signs", "stub", "acr_flank_narr"),
  H("alt_abd", "Other abdominal cause (appendicitis, diverticulitis, ovarian torsion)", "Other abdominal", "must_not_miss", "Atypical features", "partial", "acr_flank_old")],
 "steps": [
  ST("Noncontrast CT", "Nonpregnant adults without known stones", "Imaging study of choice.", {
   "stone": E("conf", "Reliably shows stone size, position and complications.", "acr_flank"),
   "alt_abd": E("conf", "Also diagnoses other causes of abdominal pain.", "acr_flank")}),
  ST("Ultrasound", "Pregnancy, or to look for obstruction", "First choice in pregnancy; less sensitive for stones.", {
   "stone": E("steer", "Shows obstruction; MRI may follow in pregnancy.", "acr_flank")}),
  ST("Contrast CT or MRI", "Noncontrast CT inconclusive", "Second-line imaging.", {
   "stone": E("conf", "CT urogram or MRI may be appropriate.", "acr_flank")})],
 "rules": {
  "stone": RULES("ACR criteria for test choice; meta-analysis data for accuracy.",
   [R("No stone or secondary signs on noncontrast CT: pooled sensitivity 94 to 100% in a meta-analysis.", "relias_nephro"),
    R("Low-dose CT performs similarly (negative likelihood ratio about 0.04) for stones of 2 to 3 mm or more.", "bestbets_ldct")],
   [R("Ultrasound alone to exclude a stone; it is less sensitive.", "acr_flank")]),
  "pyelo": RULES("Not yet researched.", [], [], "Separate ACR pyelonephritis topic not sourced."),
  "alt_abd": RULES("Comparative study.", [],
   [R("A stone-protocol CT as proof that nothing else is wrong; one study found 74% sensitivity for alternative causes.", "flank_alt_study")],
   "No reliable exclusion rule; noncontrast CT missed about a quarter of alternative causes in one study.")},
 "gaps": [GAP("Vascular causes", "Aortic aneurysm as a flank pain mimic was not sourced.", None)]
}

FEVER = {
 "id": "fever_sepsis", "title": "Fever in an adult (suspected sepsis)", "setting": "Emergency department and wards", "population": "Adults",
 "priority": "Fever is among the top ED reasons for visit in NHAMCS fact sheets.", "priority_source": "nhamcs_2011",
 "lead_guidelines": ["ssc_2026", "ssc_2026_exec"], "status": "partial",
 "layer0": [
  L0("Signs of infection and vital signs", "Screened with NEWS/NEWS2, MEWS or SIRS rather than qSOFA alone.", "epocrates_ssc_2026"),
  L0("Sepsis certainty", "The 2026 guideline grades suspected sepsis as definite, probable, possible or unlikely.", "ssc_2026_exec")],
 "gate": [
  G(True, "Probable or definite sepsis, or shock", "Treat as an emergency: antimicrobials within 1 hour of recognition.", "umem_ssc_2026"),
  G(False, "Possible sepsis without shock", "Time-limited investigation; if infection is likely, antimicrobials within 3 hours.", "umem_ssc_2026")],
 "gate_note": "Updated to the 2026 Surviving Sepsis Campaign guideline, which replaced the 2021 edition.", "gate_note_source": "ssc_2026",
 "hypotheses": [
  H("sepsis", "Sepsis", "Sepsis", "must_not_miss", "Infection with organ dysfunction", "partial", "ssc_2026_exec"),
  H("men", "Bacterial meningitis", "Meningitis", "must_not_miss", "Headache, neck stiffness; see headache", "partial", "snnoop10"),
  H("pna", "Pneumonia", "Pneumonia", "other", "Respiratory signs", "partial", "tw_cp_exam"),
  H("noninf", "Non-infectious cause", "Non-infectious", "other", "Not sourced", "stub", None)],
 "steps": [
  ST("Screening tool", "At triage", "NEWS/NEWS2, MEWS or SIRS rather than qSOFA alone (strong recommendation).", {
   "sepsis": E("blind", "A negative qSOFA alone does not rule sepsis out.", "epocrates_ssc_2026")}, "epocrates_ssc_2026"),
  ST("Grade the certainty", "After screening", "Definite, probable, possible or unlikely sepsis, using the guideline's standard language.", {
   "sepsis": E("steer", "Sets urgency: 1 hour for probable or definite, a time-limited work-up for possible.", "umem_ssc_2026")}, "ssc_2026_exec"),
  ST("Time-limited investigation", "Possible sepsis without shock", "Search for infection within a set time before committing to antimicrobials.", {
   "sepsis": E("steer", "If infection becomes likely, antimicrobials within 3 hours; the guideline does not state a formal exclusion test.", "umem_ssc_2026"),
   "noninf": E("steer", "The 2026 guideline addresses noninfectious causes in possible sepsis without shock; details not extracted.", "ssc_2026")}),
  ST("Blood lactate", "Suspected sepsis", "Suggested in the 2021 edition; re-check against 2026.", {
   "sepsis": E("steer", "Elevated lactate supports sepsis and guides resuscitation (2021 statement).", "ssc_2021")}),
  ST("Source search", "In parallel", "Chest film; lumbar puncture when meningitis is suspected.", {
   "pna": E("conf", "Infiltrate on chest film confirms.", "rcem_cxr"),
   "men": E("conf", "CSF examination is the diagnostic test.", "aafp_idsa_mening")})],
 "rules": {
  "sepsis": RULES("Surviving Sepsis Campaign 2026 (lactate and procalcitonin statements still from 2021).", [],
   [R("A negative qSOFA alone.", "epocrates_ssc_2026"), R("Procalcitonin to decide whether to start antimicrobials (2021 statement; re-check).", "ssc_2021")],
   "No formal exclusion test. The 2026 guideline grades certainty and uses a time-limited investigation for possible sepsis."),
  "men": RULES("See headache situation.", [], [R("Delaying antibiotics for CT.", "ebm_lp")], "Diagnosis depends on CSF examination."),
  "pna": RULES("Educational summary.", [R("Normal chest radiograph makes it unlikely.", "rcem_cxr")], []),
  "noninf": RULES("Not yet researched.", [], [], "Named in the 2026 guideline; statements not extracted.")},
 "gaps": [
  GAP("2021 leftovers", "Lactate and procalcitonin steps still cite the 2021 edition and need checking against 2026.", "ssc_2021"),
  GAP("Children", "The 2026 pediatric Surviving Sepsis guideline is separate and not included.", None)]
}
