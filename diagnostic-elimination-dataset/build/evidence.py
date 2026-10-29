# Extra Layer 3 evidence attached to steps, keyed by (situation_id, step title).
EXTRA_EVIDENCE = {
 ("lower_abdominal_pain", "Contrast CT"): [
  {"text": "Cochrane review: at 43% prevalence, a positive CT means about a 92% chance of appendicitis and a negative CT about 4%.", "source": "cochrane_appy"}],
 ("flank_pain", "Noncontrast CT"): [
  {"text": "In one prospective comparison, CT found an alternative diagnosis in about a third of patients.", "source": "relias_nephro"},
  {"text": "For causes other than stones, noncontrast CT and ultrasound had similar accuracy (CT sensitivity 74%).", "source": "flank_alt_study"}],
 ("chest_pain", "Definitive imaging for what remains"): [
  {"text": "ESC 2024 recommends a multiparametric diagnostic algorithm using ADD-RS (class I, level B).", "source": "ecr_esc_aortic"}],
}
