from nova.config.resolver import resolve


def test_later_layers_win():
    eff = resolve({
        "commons": {"values": {"model": "sonnet", "cap": 4}},
        "team": {"values": {"cap": 6}},
        "user": {"values": {"model": "opus"}},
    })
    assert eff == {"model": "opus", "cap": 6}


def test_org_locked_always_wins():
    eff = resolve({
        "org": {"locked": {"permission_mode": "strict"}},
        "user": {"values": {"permission_mode": "yolo", "model": "opus"}},
    })
    assert eff["permission_mode"] == "strict"
    assert eff["model"] == "opus"
