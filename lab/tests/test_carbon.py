import numpy as np
import polars as pl
import pytest

from gridpilot.carbon import wait_choice, wait_cut


def test_wait_choice_picks_the_earliest_cleanest_hour_in_the_window():
    ci = np.array([10.0, 1.0, 10.0, 1.0, 10.0])
    assert wait_choice(ci, 0).tolist() == [0, 0, 0, 0, 0]
    assert wait_choice(ci, 1).tolist() == [1, 0, 1, 0, 0]
    assert wait_choice(ci, 3).tolist() == [1, 0, 1, 0, 0]  # tie at offsets 1 and 3: earliest wins
    with pytest.raises(ValueError):
        wait_choice(ci, -1)


def test_wait_cut_hand_case():
    ci = np.array([10.0, 1.0, 10.0, 10.0])
    assert wait_cut(ci, 0) == 0.0
    # Hour 0 moves to hour 1 (saves 9); the window is truncated at the end of the series.
    assert wait_cut(ci, 1) == pytest.approx(9 / 31)


def test_wait_cut_evaluates_choices_on_another_signal():
    average = np.array([10.0, 1.0, 10.0])
    flat_margin = np.array([5.0, 5.0, 5.0])
    assert wait_cut(average, 2) > 0
    assert wait_cut(average, 2, evaluate_on=flat_margin) == 0.0
    with pytest.raises(ValueError):
        wait_cut(average, 2, evaluate_on=flat_margin[:2])


def test_wait_cut_matches_the_recon_rolling_min_formula():
    # recon_grid.carbon: fut_min = reverse rolling min over W + 1 rows; cut = sum(ci - fut) / sum(ci)
    rng = np.random.default_rng(7)
    ci = rng.uniform(100, 800, size=500)
    for w in (1, 6, 24):
        fut = pl.Series(ci).reverse().rolling_min(w + 1, min_samples=1).reverse().to_numpy()
        assert wait_cut(ci, w) == pytest.approx((ci - fut).sum() / ci.sum())
