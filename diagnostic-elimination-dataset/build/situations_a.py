# Effect types: rule = can eliminate, conf = can confirm, steer = shifts suspicion, blind = cannot decide it
def L0(label, detail, source): return {"label": label, "detail": detail, "source": source}
def G(urgent, label, detail, source): return {"urgent": urgent, "label": label, "detail": detail, "source": source}
def H(id, name, short, tier, clue, status, clue_source=None):
    return {"id": id, "name": name, "short": short, "tier": tier, "clue": clue, "clue_source": clue_source, "status": status}
def E(t, text, source): return {"type": t, "text": text, "source": source}
def ST(title, timing, description, effects, source=None):
    return {"title": title, "timing": timing, "description": description, "source": source, "effects": effects}
def R(text, source, inferred=False): return {"text": text, "source": source, "inferred": inferred}
def RULES(validation, when, dont, none=None): return {"validation": validation, "eliminate_when": when, "do_not_rely": dont, "no_rule_note": none}
def GAP(title, text, source): return {"title": title, "text": text, "source": source}

# =====================================================================
CHEST_PAIN = {
 "id": "chest_pain", "title": "Acute chest pain", "setting": "Emergency department or clinic", "population": "Adults",
 "priority": "Second most common ED reason for visit in NHAMCS fact sheets.", "priority_source": "nhamcs_2011",
 "lead_guidelines": ["aha_cp_top", "aha_cp_rec", "esc_aortic_2024"], "status": "partial",
 "layer0": [
  L0("Complaint", "Pain, pressure, tightness or discomfort in the chest, shoulders, arms, neck, back, upper abdomen or jaw; shortness of breath and fatigue count as equivalents.", "aha_cp_top"),
  L0("History", "Pain characteristics, accompanying symptoms and cardiac risk factors.", "cchcs_cp"),
  L0("Vitals and exam", "Sweating and fast breathing lean toward ACS, fast heart rate and dyspnea toward PE, air under the skin toward esophageal rupture; chest wall tenderness or pain on inspiration leans noncardiac.", "aafp_cp"),
  L0("12-lead ECG", "Recorded and read within 10 minutes of arrival.", "aafp_cp")],
 "gate": [
  G(True, "Unstable or ECG emergency", "Ongoing ischemic discomfort, dynamic ECG change, hemodynamic instability or serious arrhythmia: emergency escalation.", "iatrox_cp"),
  G(False, "Stable, ECG non-diagnostic", "Work through the hypotheses, must-not-miss first, with serial high-sensitivity troponin.", "iatrox_cp")],
 "gate_note": "One normal ECG or one early troponin does not rule out ACS; patient characteristics must not be used to dismiss the complaint.",
 "gate_note_source": "iatrox_cp",
 "hypotheses": [
  H("acs", "Acute coronary syndrome", "ACS", "must_not_miss", "Sweating, fast breathing", "partial", "aafp_cp"),
  H("pe", "Pulmonary embolism", "PE", "must_not_miss", "Fast heart rate, dyspnea", "sourced", "aafp_cp"),
  H("ad", "Aortic dissection", "Dissection", "must_not_miss", "Abrupt, tearing pain; pulse or BP differential", "sourced", "mdcalc_addrs"),
  H("ptx", "Pneumothorax", "Pneumothorax", "other", "Dyspnea, one-sided absent breath sounds", "partial", "tw_cp_exam"),
  H("pna", "Pneumonia", "Pneumonia", "other", "Fever, localized pleuritic pain", "partial", "tw_cp_exam"),
  H("pc", "Pericardial disease", "Pericardial", "other", "Positional pain, friction rub", "partial", "radio_peri"),
  H("er", "Esophageal rupture", "Esoph. rupture", "other", "Air under the skin", "stub", "aafp_cp"),
  H("nc", "Common noncardiac causes", "Noncardiac", "other", "Chest wall tenderness, pain on inspiration", "stub", "aafp_cp")],
 "steps": [
  ST("Focused history and exam", "First minutes", "Sets pre-test probability and picks the hypotheses to chase.", {
   "acs": E("steer", "Sweating and fast breathing raise suspicion.", "aafp_cp"),
   "pe": E("steer", "Fast heart rate and dyspnea raise suspicion.", "aafp_cp"),
   "ad": E("steer", "Abrupt, severe or tearing pain, pulse or BP differential, perfusion deficit.", "mdcalc_addrs"),
   "ptx": E("steer", "Dyspnea, pain on inspiration, absent breath sounds on one side.", "tw_cp_exam"),
   "pna": E("steer", "Fever, localized pleuritic pain, dullness to percussion.", "tw_cp_exam"),
   "pc": E("steer", "Pleuritic, positional pain easing when leaning forward; friction rub.", "radio_peri"),
   "er": E("steer", "Air under the skin.", "aafp_cp"),
   "nc": E("steer", "Chest wall tenderness or pain on inspiration points here.", "aafp_cp")}),
  ST("12-lead ECG", "Within 10 minutes of arrival", "Best initial test; triggers the emergency pathway when ischemic.", {
   "acs": E("blind", "Ischemic or dynamic change escalates; one normal ECG does not rule ACS out.", "iatrox_cp"),
   "pc": E("steer", "New widespread ST elevation or PR depression counts toward the two-of-four criteria.", "radio_peri")}, "acc_ed_cp"),
  ST("Chest radiograph", "After clinical assessment and ECG", "Class 1 recommendation to look for other cardiac, pulmonary and thoracic causes.", {
   "ptx": E("rule", "Normal film with distress, pleuritic pain and hypoxia excludes it; absent vascular markings is diagnostic.", "rcem_cxr"),
   "pna": E("conf", "Infiltrate or consolidation confirms; a normal film makes it unlikely.", "rcem_cxr"),
   "acs": E("blind", "No specific finding for ACS.", "rcem_cxr"),
   "pe": E("steer", "Often normal; with other causes excluded, a normal film raises PE probability.", "rcem_cxr"),
   "ad": E("blind", "Mediastinal widening helps, but a film cannot rule out aortic syndromes at low probability.", "ebm_addrs"),
   "er": E("steer", "Air in the mediastinum contributes.", "rcem_cxr"),
   "pc": E("blind", "Recommended but does not establish the diagnosis.", "esc_peri_comments")}, "aha_cp_rec"),
  ST("Serial high-sensitivity troponin and risk class", "Early, repeated per assay protocol", "Feeds the clinical decision pathway (low, intermediate, high risk).", {
   "acs": E("rule", "Low-risk class with non-ischemic ECG and negative serial troponin: no further acute testing.", "aha_cp_top"),
   "pc": E("blind", "Recommended in suspected pericarditis but not diagnostic.", "esc_peri_comments")}, "aha_cp_rec"),
  ST("Pre-test scoring of what is left", "In parallel, for open must-not-miss causes", "A validated score sets the probability band that selects the next test.", {
   "pe": E("steer", "Wells two-level score; PERC first if suspicion is very low.", "oep_vte"),
   "ad": E("steer", "ADD-RS 0 to 3: above 1 goes straight to imaging, 1 or less to D-dimer.", "mdcalc_addrs")}),
  ST("D-dimer", "Only at low or intermediate probability", "Rule-out blood test; never confirms.", {
   "pe": E("rule", "Wells 4 or less and D-dimer below the age-adjusted cutoff.", "evi_wells"),
   "ad": E("rule", "ADD-RS 1 or less and D-dimer below 500 ng/mL (FEU): consider stopping; not externally validated.", "mdcalc_addrs")}),
  ST("Definitive imaging for what remains", "For hypotheses not yet eliminated", "Settles what earlier steps could not.", {
   "pe": E("rule", "CT pulmonary angiography: positive confirms, negative excludes.", "evi_wells"),
   "ad": E("conf", "ECG-gated contrast CT from neck to pelvis is the recommended first-line imaging.", "ecr_esc_aortic"),
   "pc": E("conf", "Echocardiography: new or worsening effusion counts toward criteria.", "esc_peri_comments"),
   "er": E("blind", "Confirmation route not yet sourced.", None)}),
  ST("If the dangerous causes are eliminated", "Last", "Noncardiac causes become the working diagnosis.", {
   "nc": E("steer", "Chest wall pain, reflux esophagitis and costochondritis are most common in primary care.", "cchcs_cp"),
   "acs": E("steer", "Low-risk patients do not need urgent stress testing or imaging.", "aha_cp_top")})],
 "rules": {
  "acs": RULES("Sourced to AHA/ACC 2021 summaries.",
   [R("Low-risk class on the clinical decision pathway: non-ischemic ECG and negative serial high-sensitivity troponin.", "aha_cp_top"),
    R("Low-risk patients gain nothing from stress testing or imaging within 30 days.", "aafp_cp")],
   [R("One normal ECG or one early troponin.", "iatrox_cp"), R("The chest radiograph.", "rcem_cxr"),
    R("Dismissing the complaint because of sex, age, race, language or anxiety history.", "iatrox_cp"),
    R("Assuming acute troponin is available everywhere.", "cchcs_cp")]),
  "pe": RULES("Secondary summaries of ESC and NICE; verify against originals.",
   [R("Very low suspicion and all eight PERC criteria met.", "oep_vte"),
    R("Wells 4 or less and D-dimer below the age-adjusted cutoff.", "evi_wells"),
    R("Negative CT pulmonary angiography.", "evi_wells")],
   [R("D-dimer when clinical probability is high.", "iatrox_pe"), R("A normal chest radiograph.", "rcem_cxr"),
    R("The standard Wells route in unstable or pregnant patients.", "evi_wells")]),
  "ad": RULES("ESC 2024 recommends an ADD-RS-based diagnostic algorithm (class I, level B); MDCalc notes ADD-RS plus D-dimer lacks external validation.",
   [R("ADD-RS 1 or less and D-dimer below 500 ng/mL (FEU): consider stopping the work-up.", "mdcalc_addrs"),
    R("In ADvISED this strategy missed about 0.3% of acute aortic syndromes.", "advised"),
    R("In the later PROFUNDUS study, ADD-RS 1 or less with negative D-dimer had a 0.2% failure rate.", "aas_review_2025"),
    R("Negative ECG-gated contrast CT, the first-line imaging in ESC 2024 (class I, level C).", "ecr_esc_aortic", True)],
   [R("D-dimer alone.", "advised"), R("ADD-RS of 0 as proof.", "litfl_addrs"), R("Chest radiography.", "ebm_addrs"),
    R("A D-dimer threshold in the wrong units (assumes FEU).", "mdcalc_addrs")]),
  "ptx": RULES("Educational summary of the guideline.",
   [R("Normal chest radiograph with respiratory distress, pleuritic pain and hypoxia.", "rcem_cxr")],
   [R("Exam findings alone.", "tw_cp_exam")]),
  "pna": RULES("Educational summary of the guideline.",
   [R("Normal chest radiograph makes it unlikely, not impossible.", "rcem_cxr")],
   [R("Exam findings alone.", "tw_cp_exam")]),
  "pc": RULES("Diagnostic criteria only; no exclusion rule found.", [],
   [R("A normal ECG: without ST elevation the diagnosis is easily missed.", "peri_book"),
    R("Chest film, markers or troponin as diagnostic; only ECG and echo help establish it.", "esc_peri_comments")],
   "No formal exclusion rule found. Diagnosis needs at least two of four criteria."),
  "er": RULES("Not yet researched.", [], [], "No elimination rule sourced yet."),
  "nc": RULES("Diagnosis of exclusion.", [],
   [R("Chest wall tenderness alone.", "aafp_cp")], "Not eliminated; it is what remains.")},
 "gaps": [
  GAP("Local resources", "Some sites cannot run acute troponin, so the pathway cannot be applied as written.", "cchcs_cp"),
  GAP("Which PE score", "Wells, revised Geneva and YEARS lead to the same next steps, but protocols differ.", "iatrox_pe"),
  GAP("US versus Europe on dissection", "ESC 2024 sends ADD-RS 2 or more to CT regardless of D-dimer; AHA guidance lacks consensus on the ADD-RS cut-off and on D-dimer.", "aas_review_2025"),
  GAP("Parallel hypotheses", "No source found on prioritizing ACS, PE and dissection work-ups run at the same time.", None)]
}

# =====================================================================
HEADACHE = {
 "id": "headache", "title": "Acute nontraumatic headache", "setting": "Emergency department", "population": "Adults",
 "priority": "Among the top five ED reasons for visit in NHAMCS fact sheets.", "priority_source": "nhamcs_2011",
 "lead_guidelines": ["acep_headache", "snnoop10"], "status": "partial",
 "layer0": [
  L0("Complaint", "New or different headache; how fast it reached peak intensity (peak within 1 hour matters for the SAH rule).", "acep_headache"),
  L0("History: red flags", "SNNOOP10: systemic symptoms including fever, cancer history, neurologic deficit, sudden onset, onset after 65, new or changed pattern, positional, triggered by cough or exertion, papilledema, progressive, pregnancy, painful eye with autonomic features, trauma, immune compromise, painkiller overuse or new drug.", "snnoop10"),
  L0("Exam", "Full neurologic exam, level of consciousness, neck pain or stiffness, limited neck flexion, papilledema, fever.", "acep_headache")],
 "gate": [
  G(True, "Neurologic deficit or decreased consciousness", "A red flag for a secondary cause; the ACEP rule-out tools below do not apply because they assume a normal neurologic exam.", "acep_headache"),
  G(False, "Alert, normal neurologic exam", "Screen red flags, then apply the SAH rule if the headache peaked within 1 hour.", "acep_headache")],
 "gate_note": "Most headaches are primary, but secondary causes must be screened for first.",
 "gate_note_source": "jin_headache",
 "hypotheses": [
  H("sah", "Subarachnoid hemorrhage", "SAH", "must_not_miss", "Thunderclap onset, exertion, neck stiffness", "sourced", "acep_headache"),
  H("men", "Bacterial meningitis", "Meningitis", "must_not_miss", "Fever and systemic signs", "partial", "snnoop10"),
  H("sec", "Other secondary headache", "Other secondary", "must_not_miss", "Any SNNOOP10 red flag", "partial", "snnoop10"),
  H("prim", "Primary headache (migraine, tension-type)", "Primary", "other", "No red flags", "partial", "jin_headache")],
 "steps": [
  ST("Red-flag history (SNNOOP10)", "First minutes", "Structured screen of every new or different headache.", {
   "sah": E("steer", "Sudden or thunderclap onset is a red flag.", "snnoop10"),
   "men": E("steer", "Fever and systemic symptoms are a red flag.", "snnoop10"),
   "sec": E("steer", "Each flag raises suspicion, but specificity is not validated.", "snnoop10"),
   "prim": E("steer", "With no red flags, primary headache becomes more likely.", "jin_headache")}),
  ST("Neurologic exam", "First minutes", "Decides which rules can be used.", {
   "sah": E("blind", "Neck stiffness is strongly associated, but no single sign rules SAH out.", "acep_headache"),
   "men": E("steer", "Abnormal consciousness or focal deficit means CT before lumbar puncture.", "cam_ct_study"),
   "sec": E("steer", "A deficit or papilledema is a red flag.", "snnoop10")}),
  ST("Ottawa SAH rule", "Alert patients, normal neuro exam, peak within 1 hour", "Six features: age 40 or older, neck pain or stiffness, witnessed loss of consciousness, onset with exertion, thunderclap onset, limited neck flexion.", {
   "sah": E("rule", "None present: high sensitivity supports ruling SAH out; any present only means investigate (low specificity).", "acep_headache")}),
  ST("Noncontrast head CT", "As early as possible", "First imaging test for suspected SAH and before LP in at-risk patients.", {
   "sah": E("rule", "Normal CT within 6 hours of onset, with normal neuro exam, rules out nontraumatic SAH.", "acep_headache"),
   "men": E("steer", "Only needed before LP if immunocompromised, CNS disease, new seizure, papilledema, abnormal consciousness or focal deficit.", "cam_ct_study")}),
  ST("Lumbar puncture or CT angiography", "If still at risk after a negative CT", "Second-line test chosen with the patient.", {
   "sah": E("rule", "LP or CTA safely rules out SAH in a patient still at risk after a negative CT.", "mdcalc_acep_headache"),
   "men": E("conf", "Diagnosis depends on CSF examination; blood cultures and LP should be done promptly.", "aafp_idsa_mening")}),
  ST("If no red flags and secondary causes are excluded", "Last", "Primary headache becomes the working diagnosis.", {
   "prim": E("steer", "Diagnosis of exclusion once red flags are absent or answered.", "jin_headache")})],
 "rules": {
  "sah": RULES("ACEP 2019 clinical policy.",
   [R("Ottawa SAH rule negative in an alert patient with normal neuro exam and peak within 1 hour.", "acep_headache"),
    R("Normal noncontrast CT within 6 hours of onset with normal neuro exam.", "acep_headache"),
    R("Negative LP or CTA after a negative CT in a patient still at risk.", "mdcalc_acep_headache")],
   [R("A single sign or symptom.", "acep_headache"),
    R("The Ottawa rule outside its population (abnormal neuro exam, slower peak).", "acep_headache"),
    R("A positive Ottawa rule as proof; it has low specificity.", "acep_headache")]),
  "men": RULES("IDSA 2004 via secondary summaries; check for newer guidance.", [],
   [R("Delaying antibiotics for CT; cultures and antibiotics come first when CT is needed.", "ebm_lp"),
    R("A normal head CT as proof that LP is safe in every patient.", "ebm_lp")],
   "No formal exclusion rule sourced; diagnosis depends on CSF examination."),
  "sec": RULES("Red flags from a narrative review.", [],
   [R("Imaging everyone; many scans find nothing relevant.", "snnoop10")],
   "No single elimination rule; each secondary cause needs its own route."),
  "prim": RULES("Diagnosis of exclusion.", [], [], "Not eliminated; it is what remains when red flags are absent.")},
 "gaps": [
  GAP("Rule validation", "Early reviews noted the Ottawa SAH rule had mainly Canadian validation; check local validity.", "rebel_ottawa"),
  GAP("CT/LP versus CT/CTA", "ACEP recommends shared decision making between the two second-line strategies.", "acep_headache"),
  GAP("Red-flag evidence", "Most red flags lack prospective data on specificity.", "snnoop10")]
}

# =====================================================================
SYNCOPE = {
 "id": "syncope", "title": "Syncope (transient loss of consciousness)", "setting": "Emergency department", "population": "Adults",
 "priority": "Common ED presentation with its own US and European guidelines.", "priority_source": None,
 "lead_guidelines": ["acc_syncope_2017", "acc_esc_syncope"], "status": "partial",
 "layer0": [
  L0("The event", "Prodrome, position (standing, sitting, supine), exertion, palpitations, triggers such as pain, cough, micturition or prolonged standing.", "esc_syncope_table"),
  L0("History", "Structural heart disease or prior myocardial infarction, family history of sudden cardiac death at a young age.", "esc_syncope_table"),
  L0("Exam", "Physical examination including lying and standing blood pressure.", "syncope_risk_review"),
  L0("12-lead ECG", "Useful in the initial evaluation (class I).", "acc_syncope_2017")],
 "gate": [
  G(True, "Any high-risk feature", "New chest discomfort, breathlessness, abdominal pain or headache; syncope during exertion or supine; palpitations right before syncope; structural heart disease. Evaluate in hospital or with ECG monitoring.", "esc_syncope_table"),
  G(False, "Low-risk features only", "Typical reflex prodrome or trigger, or syncope on standing up. Likely reflex or orthostatic; discharge can be considered.", "sec_syncope")],
 "gate_note": "Not all high-risk patients need admission; risk scores may be reasonable but are not better than clinical judgment.",
 "gate_note_source": "aafp_syncope",
 "hypotheses": [
  H("card", "Cardiac (arrhythmic or structural) syncope", "Cardiac", "must_not_miss", "Exertional or supine, palpitations, heart disease", "partial", "esc_syncope_table"),
  H("serious", "Serious condition presenting as syncope", "Serious other", "must_not_miss", "New chest pain, breathlessness, abdominal pain or headache", "stub", "esc_syncope_table"),
  H("orth", "Orthostatic hypotension", "Orthostatic", "other", "Syncope on standing", "partial", "esc_syncope_table"),
  H("reflex", "Reflex (vasovagal, situational) syncope", "Reflex", "other", "Prodrome, typical triggers", "partial", "esc_syncope_table")],
 "steps": [
  ST("Event history", "First minutes", "Separates low-risk reflex patterns from high-risk features.", {
   "card": E("steer", "Exertion, supine position, sudden palpitations, or no or very short prodrome with heart disease.", "esc_syncope_table"),
   "serious": E("steer", "New chest discomfort, breathlessness, abdominal pain or headache is a major high-risk feature.", "esc_syncope_table"),
   "orth": E("steer", "Syncope on standing up from lying or sitting.", "esc_syncope_table"),
   "reflex": E("steer", "Prodrome of light-headedness, warmth, sweating or nausea; pain, crowded hot places, cough or micturition triggers.", "esc_syncope_table")}),
  ST("Exam with lying and standing blood pressure", "Initial evaluation", "Part of the standard initial evaluation.", {
   "orth": E("steer", "Lying and standing BP is the bedside test for orthostatic causes.", "syncope_risk_review"),
   "card": E("steer", "Findings of structural heart disease are high risk.", "esc_syncope_table")}),
  ST("12-lead ECG", "Initial evaluation", "Class I in the initial evaluation.", {
   "card": E("steer", "An abnormal ECG turns minor features into high-risk ones.", "esc_syncope_table")}, "acc_syncope_2017"),
  ST("Risk stratification and disposition", "After history, exam and ECG", "Sorts patients into high, intermediate and low risk.", {
   "card": E("steer", "Low-risk features only: discharge from the ED is recommended for patients without recurrence.", "sec_syncope"),
   "reflex": E("steer", "Low-risk patients mostly have reflex syncope with a good prognosis.", "sec_syncope")}),
  ST("Targeted tests only when suspected", "Selected patients", "Routine labs, cardiac imaging and carotid imaging are not useful without a specific reason.", {
   "card": E("conf", "ECG monitoring in high-risk patients with suspected arrhythmia; cardiac imaging only if a cardiac cause is suspected.", "acc_esc_syncope"),
   "reflex": E("conf", "Tilt testing when reflex syncope is suspected.", "acc_esc_syncope"),
   "orth": E("conf", "Tilt testing when an orthostatic cause is suspected.", "acc_esc_syncope")})],
 "rules": {
  "card": RULES("ESC 2018 and ACC/AHA/HRS 2017 summaries.",
   [R("Only low-risk features after history, exam and ECG: ESC 2018 recommends discharge from the ED (class I, level B). Treating this disposition as elimination is the inferred part.", "sec_syncope", True)],
   [R("Routine comprehensive laboratory testing.", "acc_syncope_2017"),
    R("Routine cardiac imaging without a suspected cardiac cause.", "acc_syncope_2017"),
    R("Risk scores as better than clinical judgment.", "aafp_syncope")]),
  "serious": RULES("Not yet researched.", [], [], "Route depends on the underlying condition (for example PE or dissection); see the chest pain situation."),
  "orth": RULES("Partly sourced.", [], [R("Carotid imaging without focal neurologic findings.", "acc_syncope_2017")], "No elimination threshold extracted; orthostatic criteria are in the ESC guideline."),
  "reflex": RULES("Partly sourced.", [], [], "Diagnosis is clinical; tilt testing when suspected.")},
 "gaps": [
  GAP("Two guidelines", "US (2017) and European (2018) guidelines overlap but differ in detail.", "acc_esc_syncope"),
  GAP("Intermediate risk", "Patients with neither high- nor low-risk features have no single sourced pathway here.", None),
  GAP("Orthostatic thresholds", "Exact blood pressure criteria were not extracted in this pass.", None)]
}


# Extra Layer 3 evidence attached to steps (by step title)
CHEST_PAIN_EVIDENCE = {
 "Pre-test scoring of what is left": [
  {"text": "PE incidence is about 12% in the Wells unlikely band and about 37% in the likely band.", "source": "wikem_wells"},
  {"text": "About 95% of patients with acute aortic dissection score intermediate or high on ADD-RS.", "source": "rcem_addrs"},
  {"text": "Meta-analysis: ADD-RS of 1 or more is about 94% sensitive alone and close to 100% with D-dimer; the best threshold depends on setting.", "source": "addrs_meta"}]}
for _st in CHEST_PAIN["steps"]:
    _st["evidence"] = CHEST_PAIN_EVIDENCE.get(_st["title"], [])
