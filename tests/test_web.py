import pytest
from flask import Flask, render_template_string

from general_standard_functions.web.csrf import INVALID_TOKEN_MESSAGE, init_csrf
from general_standard_functions.web.errors import register_error_page


@pytest.fixture
def app(tmp_path):
    (tmp_path / "fout.html").write_text("Er ging iets mis", encoding="utf-8")
    app = Flask(__name__, template_folder=str(tmp_path))
    app.secret_key = "test"
    init_csrf(app, fallback_endpoint="home")
    register_error_page(app, "fout.html")

    @app.route("/")
    def home():
        return "home"

    @app.route("/form", methods=["GET", "POST"])
    def form():
        return render_template_string("<form>{{ csrf_field() }}</form>")

    @app.route("/boom")
    def boom():
        raise RuntimeError('relation "users" does not exist: SELECT * FROM users')

    return app


def _token(client) -> str:
    html = client.get("/form").get_data(as_text=True)
    return html.split('value="', 1)[1].split('"', 1)[0]


def test_post_with_valid_token_passes(app):
    client = app.test_client()
    response = client.post("/form", data={"csrf_token": _token(client)})
    assert response.status_code == 200


def test_post_without_token_is_redirected_with_message(app):
    client = app.test_client()
    response = client.post("/form", data={})
    assert response.status_code == 302 and response.location.endswith("/")
    with client.session_transaction() as session:
        assert (session["_flashes"][0][1]) == INVALID_TOKEN_MESSAGE


def test_redirect_goes_back_only_to_own_site(app):
    client = app.test_client()
    own = client.post("/form", headers={"Referer": "http://localhost/form"})
    foreign = client.post("/form", headers={"Referer": "https://evil.example/"})
    assert own.location.endswith("/form")
    assert foreign.location.endswith("/") and "evil" not in foreign.location


def test_csrf_can_be_disabled_for_tests(app):
    app.config["CSRF_ENABLED"] = False
    assert app.test_client().post("/form").status_code == 200


def test_error_page_hides_details(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = app.test_client().get("/boom")
    html = response.get_data(as_text=True)
    assert response.status_code == 500 and "Er ging iets mis" in html
    assert "SELECT" not in html and "relation" not in html
