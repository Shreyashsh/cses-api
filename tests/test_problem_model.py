# tests/test_problem_model.py
from models.problem import Problem


def test_problem_model_without_redundant_alias():
    """Problem model should work without redundant aliases."""
    problem = Problem(
        id="1",
        title="Test Problem",
        category="test",
        input_format="stdin",
        output_format="stdout",
    )
    assert problem.input_format == "stdin"
    assert problem.output_format == "stdout"


def test_problem_model_json_serialization():
    """Problem model should serialize correctly."""
    problem = Problem(
        id="1",
        title="Test Problem",
        category="test",
        input_format="stdin",
        output_format="stdout",
    )
    data = problem.model_dump()
    assert data["input_format"] == "stdin"
    assert data["output_format"] == "stdout"
