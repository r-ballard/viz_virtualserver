import pytest

from lsystem.geometry import GeometryError, commands_to_geometry


def geometry(commands: str, angle: float = 90.0):
    return commands_to_geometry(
        commands,
        generation=0,
        step=1.0,
        angle_degrees=angle,
        initial_heading_degrees=0.0,
        draw_symbols={"F"},
        move_symbols={"f"},
    )


def test_square_is_precomputed_as_one_polyline():
    result = geometry("F+F+F+F")
    assert result.segment_count == 4
    assert len(result.paths) == 1
    expected = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
    for point, expected_point in zip(result.paths[0], expected, strict=True):
        assert point == pytest.approx(expected_point, abs=1e-12)


def test_branch_splits_paths_without_drawing_return_jump():
    result = geometry("F[+F]F")
    assert result.segment_count == 3
    assert len(result.paths) == 3
    expected_paths = [
        [(0, 0), (1, 0)],
        [(1, 0), (1, 1)],
        [(1, 0), (2, 0)],
    ]
    for path, expected_path in zip(result.paths, expected_paths, strict=True):
        for point, expected_point in zip(path, expected_path, strict=True):
            assert point == pytest.approx(expected_point, abs=1e-12)


def test_unbalanced_branch_is_rejected():
    with pytest.raises(GeometryError, match="unmatched"):
        geometry("F[F")
