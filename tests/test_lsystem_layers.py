from lsystem.layers import resolve_pen_layers


def test_seventeen_generations_partition_across_eight_pens():
    layers = resolve_pen_layers(generations=16, explicit_layers=None)
    assert [(item.pen, item.start_generation, item.end_generation) for item in layers] == [
        (1, 0, 1),
        (2, 2, 3),
        (3, 4, 5),
        (4, 6, 7),
        (5, 8, 9),
        (6, 10, 11),
        (7, 12, 13),
        (8, 14, 16),
    ]
