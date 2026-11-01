from evaluation.metrics import wilson, macro_f1, mcnemar_exact, bootstrap_ci, confidence_table


def test_wilson_and_f1():
    lo, hi = wilson(28, 30); assert 0.78 < lo < 0.93 < hi <= 1
    assert macro_f1(["a", "b"], ["a", "b"]) == 1.0 and macro_f1(["a", "a"], ["b", "b"]) == 0.0


def test_mcnemar_and_bootstrap():
    assert mcnemar_exact([1, 1, 0], [1, 1, 0]) == 1.0
    assert mcnemar_exact([1] * 10 + [0] * 10, [0] * 10 + [0] * 10) < 0.01
    lo, hi = bootstrap_ci(["a", "b"] * 10, ["a", "b"] * 10, macro_f1, 200); assert lo == hi == 1.0
    assert len(confidence_table([0.5, 0.9], [False, True])) == 4
