import pytest
from http import HTTPStatus
from sqlalchemy.exc import DatabaseError

from pbench.server.database.models.template import Template


@pytest.fixture()
def database_error(monkeypatch):
    def raise_db_error(name: str):
        raise DatabaseError("DB Error")

    with monkeypatch.context() as m:
        m.setattr(Template, "find", raise_db_error)
        yield


class TestIndexMappings:
    """
    Unit testing for resources/IndexMappings class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def test_run_template_query(self, client, server_config, find_template):
        """
        Check the construction of index mappings API and filtering of the
        response body.
        """
        with client:
            response = client.get(f"{server_config.rest_uri}/index/mappings/run")
            assert response.status_code == HTTPStatus.OK
            res_json = response.json
            assert res_json == {
                "@metadata": [
                    "controller_dir",
                    "file-date",
                    "file-name",
                    "file-size",
                    "md5",
                    "pbench-agent-version",
                    "raw_size",
                    "result-prefix",
                    "satellite",
                    "tar-ball-creation-timestamp",
                    "toc-prefix",
                ],
                "authorization": ["access", "owner"],
                "host_tools_info": [
                    "hostname",
                    "hostname-f",
                    "hostname-s",
                    "label",
                    "tools",
                ],
                "run": [
                    "config",
                    "controller",
                    "date",
                    "end",
                    "id",
                    "iterations",
                    "name",
                    "script",
                    "start",
                    "toolsgroup",
                    "user",
                ],
                "sosreports": [
                    "hostname-f",
                    "hostname-s",
                    "inet",
                    "inet6",
                    "md5",
                    "name",
                    "sosreport-error",
                ],
            }

    def test_result_template_query(self, client, server_config, find_template):
        """
        Check the construction of index mappings API and filtering of the
        response body.
        """
        with client:
            response = client.get(f"{server_config.rest_uri}/index/mappings/result")
            assert response.status_code == HTTPStatus.OK
            res_json = response.json
            assert res_json == {
                "iteration": ["name", "number"],
                "result": ["@idx", "read_or_write", "value"],
                "run": ["id", "name"],
                "sample": [
                    "@idx",
                    "name",
                    "measurement_type",
                    "measurement_idx",
                    "measurement_title",
                    "uid",
                ],
            }

    def test_with_no_index_document(self, client, server_config):
        """
        Check the index mappings API if there is no index document (specified by the index name in the URI)
        present in the database.
        """
        with client:
            response = client.get(f"{server_config.rest_uri}/index/mappings/run")
            assert response.status_code == HTTPStatus.NOT_FOUND
            assert response.json["message"] == "Mapping not found"

    def test_with_db_error(self, client, server_config, database_error):
        """
        Check the index mappings API if there is an error connecting to sql database.
        """
        with client:
            response = client.get(f"{server_config.rest_uri}/index/mappings/run")
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert response.json["message"] == "Internal Server Error"
