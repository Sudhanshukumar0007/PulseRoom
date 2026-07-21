from app.main import create_app


def test_create_app_registers_root_and_websocket_routes():
    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/" in paths
    assert "/ws/{room_id}" in paths
