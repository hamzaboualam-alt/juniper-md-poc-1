import random

from app.data import Condition, Dataset, Evidence, Patient
from app.game import Case


def make_dataset() -> Dataset:
    evidences = {
        "E_1": Evidence("E_1", "Do you have a fever?", False, "B", "0", {}),
        "E_2": Evidence("E_2", "Do you cough?", False, "B", "0", {}),
        "E_3": Evidence(
            "E_3", "What colour is the rash?", False, "C", "NA",
            {"NA": "NA", "V_red": "red", "V_pink": "pink"},
        ),
        "E_4": Evidence("E_4", "Did you travel recently?", True, "C", "N", {"N": "N", "V_af": "Africa"}),
    }
    conditions = {
        "Flu": Condition("Flu", "J11", 3, frozenset({"E_1", "E_2"}), frozenset()),
        "Measles": Condition("Measles", "B05", 2, frozenset({"E_1", "E_3"}), frozenset({"E_4"})),
    }
    patient = Patient(
        age=30, sex="F", pathology="Measles",
        evidences=("E_1", "E_3_@_V_red", "E_4_@_V_af"),
        initial_evidence="E_1",
        differential=(("Measles", 0.7), ("Flu", 0.3)),
    )
    return Dataset(evidences, conditions, [patient])


def test_patient_answers_from_record():
    ds = make_dataset()
    case = Case(ds, ds.random_patient(random.Random(0)))
    assert case.ask("E_1").answer == "Yes"
    assert case.ask("E_2").answer == "No"
    assert case.ask("E_3").answer == "red"
    assert case.ask("E_4").answer == "Africa"
    assert case.ask("E_1").repeat is True


def test_categorical_default_when_absent():
    ds = make_dataset()
    patient = Patient(30, "M", "Flu", ("E_1", "E_2"), "E_1", (("Flu", 1.0),))
    case = Case(ds, patient)
    assert case.ask("E_3").answer == "Not applicable"
    assert case.ask("E_4").answer == "No"


def test_grade_correct_diagnosis():
    ds = make_dataset()
    case = Case(ds, ds.patients[0])
    case.ask("E_3")
    result = case.diagnose("Measles", ["Flu"])
    assert result["exact"] is True
    assert result["truth_rank_in_doctor_ddx"] == 1
    assert result["ddx_overlap"] == 1.0
    # initial complaint E_1 plus asked E_3 out of three clues
    assert result["clues_known"] == 2 and result["clues_total"] == 3
    assert [m["code"] for m in result["missed_key_clues"]] == ["E_4"]
    assert result["verdict"].startswith("Correct: Measles")


def test_grade_wrong_diagnosis_lists_missed_clues():
    ds = make_dataset()
    case = Case(ds, ds.patients[0])
    case.ask("E_2")
    result = case.diagnose("Flu", [])
    assert result["exact"] is False
    assert result["truth_rank_in_doctor_ddx"] is None
    assert result["answer_in_reference_ddx"] is True
    assert {m["code"] for m in result["missed_key_clues"]} == {"E_3", "E_4"}
    assert "Never asked" in result["verdict"]


def test_undeterminable_is_graded_honestly():
    ds = make_dataset()
    case = Case(ds, ds.patients[0])
    result = case.diagnose(None, [], undeterminable=True)
    assert result["exact"] is False
    assert "declined to diagnose" in result["verdict"]


def test_opening_complaint_reads_first_person():
    from app.data import as_complaint

    assert as_complaint("Have you noticed a high pitched sound when breathing in?", "Yes") == "I've noticed a high pitched sound when breathing in."
    assert as_complaint("Do you have a cough?", "Yes") == "I have a cough."
    assert as_complaint("Are you experiencing shortness of breath or difficulty breathing in a significant way?", "Yes") == "I am experiencing shortness of breath or difficulty breathing in a significant way."
    assert as_complaint("Did you lose consciousness?", "Yes") == "I lost consciousness."
    assert as_complaint("Is your skin much paler than usual?", "Yes") == "My skin is much paler than usual."
    assert as_complaint("Do you have any lesions, redness or problems on your skin that you believe are related to the condition you are consulting for?", "Yes") == "I have lesions, redness or problems on my skin that I believe are related to the condition I am consulting for."
    assert as_complaint("Do you have pain somewhere, related to your reason for consulting?", "Yes") == "I'm in pain, and that's why I'm here."
    assert as_complaint("Do you feel pain somewhere?", "lower chest", "M") == "I feel pain somewhere: lower chest."


def test_hard_pool_and_normalisation():
    from app.difficulty import PRESETS, eligible, is_hard_case, normalise_condition

    ds = make_dataset()
    easy = ds.patients[0]  # Measles at 0.7, rank 1
    hard = Patient(30, "M", "Flu", ("E_1", "E_2"), "E_1", (("Measles", 0.8), ("Flu", 0.2)))
    assert is_hard_case(easy) is False and is_hard_case(hard) is True
    ds.patients.append(hard)
    assert eligible(ds, PRESETS["hard"]) == [hard]
    assert normalise_condition("measles", ds) == "Measles"
    assert normalise_condition("the flu", ds) == "Flu"
    assert normalise_condition("Pneumonia", ds) is None


def test_budget_and_unsure_answers():
    from app.difficulty import Difficulty
    from app.game import UNSURE_ANSWER, BudgetExhausted

    ds = make_dataset()
    d = Difficulty("t", max_questions=2, patient_recall=1.0)
    case = Case(ds, ds.patients[0], difficulty=d)
    first = case.ask("E_3")
    assert first.unsure and first.answer == UNSURE_ANSWER
    second = case.ask("E_3")
    assert second.answer == "red" and not second.repeat
    import pytest
    with pytest.raises(BudgetExhausted):
        case.ask("E_2")
    result = case.diagnose("measles", [])
    assert result["exact"] is True and result["unsure_answers"] == 1
    # the unsure turn did not count as uncovering the clue; the re-ask did
    assert result["clues_known"] == 2


def test_hidden_candidates_unrecognised_name_is_a_miss():
    from app.difficulty import Difficulty

    ds = make_dataset()
    case = Case(ds, ds.patients[0], difficulty=Difficulty("t", show_candidates=False))
    result = case.diagnose("Chickenpox", [])
    assert result["exact"] is False and result["unrecognised_name"] is True
    assert "not a recognised condition" in result["verdict"]


def test_baseline_doctor_plays_to_a_verdict():
    from app.baseline import GreedyDoctor
    from app.eval import play_case, summarise

    ds = make_dataset()
    rec = play_case(Case(ds, ds.patients[0]), GreedyDoctor(ds))
    assert rec["result"]["exact"] is True
    s = summarise([rec])
    assert s["n"] == 1 and s["top1"] == 1.0
