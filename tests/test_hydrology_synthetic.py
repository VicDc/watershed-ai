"""Test di idrologia su terreni sintetici con risultato atteso noto.

Le funzioni di terreno vengono da floodsim (src/floodsim/terrain.py di
3d-mountain-simulation-predicting-flood-paths, licenza MIT): definite sul
quadrato unitario, qui campionate su un raster e scalate in metri.
"""
import numpy as np
import pytest

from app.core.types import DEMGrid, FlowAlgorithm
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, _redistribute_step, simulate_flood_with_snapshots
from app.hydrology.flow_routing import (
    D8_OFFSETS, NO_FLOW, compute_flow_accumulation, compute_flow_direction, trace_flow_path,
)
from app.hydrology.priority_flood import fill_depressions

N = 61                # dispari: il centro (0.5, 0.5) cade esattamente sulla cella (30, 30)
CENTER = N // 2
RELIEF_M = 500.0


def gaussian(x, y):
    return np.exp(-5 * ((x - 0.5) ** 2 + (y - 0.5) ** 2))


def cone(x, y):
    return 1 - np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2)


def peaks(x, y):
    return (np.exp(-5 * ((x - 0.25) ** 2 + (y - 0.25) ** 2))
            + np.exp(-5 * ((x - 0.75) ** 2 + (y - 0.75) ** 2)))


def crater(x, y):
    r = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2)
    return np.exp(-5 * r) - np.exp(-20 * r)


def plane(x, y):
    return x


def make_dem(terrain) -> DEMGrid:
    rows, cols = np.mgrid[0:N, 0:N] / (N - 1)
    return DEMGrid(elevation=RELIEF_M * terrain(cols, 1 - rows), cell_size_m=30.0, origin=(0.0, 0.0))


# --- candidate detection ---------------------------------------------------

def test_gaussian_has_one_candidate_on_the_peak():
    candidates = detect_candidates(fill_depressions(make_dem(gaussian)))
    assert [(c.row, c.col) for c in candidates] == [(CENTER, CENTER)]


def test_peaks_has_one_candidate_per_peak():
    dem = make_dem(peaks)
    found = sorted((c.row, c.col) for c in detect_candidates(fill_depressions(dem)))
    # Le due gaussiane si sommano e spostano i massimi verso il centro rispetto
    # a (0.25, 0.25) e (0.75, 0.75): l'atteso è l'argmax di ciascuna metà.
    z = dem.elevation
    top_right = np.unravel_index(np.argmax(np.triu(z)), z.shape)
    bottom_left = np.unravel_index(np.argmax(np.tril(z, -1)), z.shape)
    expected = sorted([tuple(map(int, top_right)), tuple(map(int, bottom_left))])
    assert found == expected
    # restano nel quadrante del picco di partenza
    assert expected[0][0] < CENTER < expected[1][0]


# --- priority-flood ---------------------------------------------------------

def test_crater_depression_is_filled():
    dem = make_dem(crater)
    filled = fill_depressions(dem).elevation
    assert filled[CENTER, CENTER] > dem.elevation[CENTER, CENTER]
    assert filled[CENTER, CENTER] == pytest.approx(filled[CENTER - 1:CENTER + 2, CENTER - 1:CENTER + 2].min())


# --- cellular automata ------------------------------------------------------

def test_redistribution_conserves_water():
    dem = make_dem(crater)
    h = np.random.default_rng(0).random(dem.elevation.shape)
    h_new = _redistribute_step(dem.elevation, h, FLOOD_SIM_PARAMS["outflow_fraction"])
    assert h_new.sum() == pytest.approx(h.sum())


def test_flood_on_symmetric_peak_stays_symmetric():
    dem = make_dem(gaussian)
    peak = detect_candidates(dem)[0]
    _, frames = simulate_flood_with_snapshots(dem, peak, n_snapshots=1)
    h = frames[-1][1]
    assert (h >= FLOOD_SIM_PARAMS["min_depth_threshold_m"]).sum() > 1
    np.testing.assert_allclose(h, h[::-1, :], atol=1e-9)
    np.testing.assert_allclose(h, h[:, ::-1], atol=1e-9)
    np.testing.assert_allclose(h, h.T, atol=1e-9)


# --- flow routing D8 --------------------------------------------------------

def test_tilted_plane_drains_each_row_to_the_low_edge():
    accumulation = compute_flow_accumulation(make_dem(plane))
    np.testing.assert_array_equal(accumulation[:, 0], N)
    assert accumulation[:, 1:].max() == N - 1


def test_accumulation_in_sinks_counts_every_cell():
    dem = make_dem(peaks)
    sinks = compute_flow_direction(dem) == NO_FLOW
    assert compute_flow_accumulation(dem)[sinks].sum() == N * N


def test_cone_apex_drains_only_itself_and_its_path_reaches_the_border():
    dem = make_dem(cone)
    assert compute_flow_accumulation(dem)[CENTER, CENTER] == 1
    path = trace_flow_path(compute_flow_direction(dem), CENTER, CENTER)
    r, c = path[-1]
    assert r in (0, N - 1) or c in (0, N - 1)
    elevations = [dem.elevation[p] for p in path]
    assert all(a > b for a, b in zip(elevations, elevations[1:]))


def test_paths_cross_filled_lakes_and_flats():
    lake = fill_depressions(make_dem(crater))
    flat = make_dem(lambda x, y: np.zeros_like(x))
    for dem in (lake, flat):
        original = dem.elevation.copy()
        direction = compute_flow_direction(dem)
        assert (direction[1:-1, 1:-1] != NO_FLOW).all()
        r, c = trace_flow_path(direction, CENTER, CENTER)[-1]
        assert r in (0, N - 1) or c in (0, N - 1)
        np.testing.assert_array_equal(dem.elevation, original)
    # tutto il lago drena verso l'uscita: niente pozzi interni con accumulo
    accumulation = compute_flow_accumulation(lake)
    assert accumulation[1:-1, 1:-1].max() < accumulation.max()


def test_epsilon_fill_changes_elevation_only_infinitesimally():
    dem = make_dem(crater)
    plain = fill_depressions(dem).elevation
    eps = fill_depressions(dem, epsilon=True).elevation
    assert (eps >= plain).all()
    np.testing.assert_allclose(eps, plain, atol=1e-6)


def test_mfd_is_not_implemented():
    with pytest.raises(NotImplementedError):
        compute_flow_direction(make_dem(cone), FlowAlgorithm.MFD)


# --- flow routing D-infinity ------------------------------------------------

DINF = FlowAlgorithm.D_INFINITY


def oblique_plane(x, y):
    """Piano che scende verso est-nord-est: direzione (1, 0.5), non multipla di 45°."""
    return 1.5 - x - 0.5 * y


def test_dinf_tilted_plane_flows_west_like_d8():
    dem = make_dem(plane)
    angle = compute_flow_direction(dem, DINF)
    np.testing.assert_allclose(angle[:, 1:], np.pi)
    np.testing.assert_allclose(compute_flow_accumulation(dem, DINF)[:, 0], N)


def test_dinf_recovers_oblique_direction_that_d8_cannot():
    dem = make_dem(oblique_plane)
    expected = np.arctan2(0.5, 1.0)  # ~26.6°, tra est (D8: 0°) e nord-est (D8: 45°)
    angle = compute_flow_direction(dem, DINF)
    np.testing.assert_allclose(angle[1:, :-1], expected, atol=1e-9)

    d8 = compute_flow_direction(dem)[1:-1, 1:-1]
    d8_angles = {D8_OFFSETS[k] for k in np.unique(d8)}
    assert d8_angles <= {(0, 1), (-1, 1)}  # D8 sceglie solo E o NE


def test_dinf_cone_flows_radially_outward():
    dem = make_dem(cone)
    angle = compute_flow_direction(dem, DINF)
    rows, cols = np.mgrid[0:N, 0:N]
    radial = np.arctan2(CENTER - rows, cols - CENTER) % (2 * np.pi)
    far = np.hypot(rows - CENTER, cols - CENTER) >= 5
    interior = np.zeros_like(far)
    interior[1:-1, 1:-1] = True
    error = np.angle(np.exp(1j * (angle - radial)))  # differenza angolare in [-pi, pi]
    assert np.abs(error[far & interior]).max() < 0.1


def test_dinf_accumulation_conserves_water_and_splits_flow():
    dem = make_dem(oblique_plane)
    accumulation = compute_flow_accumulation(dem, DINF)
    sinks = np.isnan(compute_flow_direction(dem, DINF))
    assert accumulation[sinks].sum() == pytest.approx(N * N)
    # con l'acqua divisa tra due vicini compaiono accumuli frazionari
    assert not np.allclose(accumulation, np.round(accumulation))


def test_dinf_crosses_filled_lakes():
    lake = fill_depressions(make_dem(crater))
    angle = compute_flow_direction(lake, DINF)
    assert not np.isnan(angle[1:-1, 1:-1]).any()
    accumulation = compute_flow_accumulation(lake, DINF)
    assert accumulation[np.isnan(angle)].sum() == pytest.approx(N * N)
