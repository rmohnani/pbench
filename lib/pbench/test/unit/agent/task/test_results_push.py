import logging
import os
from http import HTTPStatus

import requests
import responses
from click.testing import CliRunner

from pbench.cli.agent.commands.results.push import main
from pbench.test.unit.agent.task.common import bad_tarball, tarball


class TestResultsPush:

    CTRL_TEXT = "controller.example.com"
    TOKN_SWITCH = "--token"
    TOKN_PROMPT = "Token: "
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    URL = "http://pbench.example.com/api/v1"

    @staticmethod
    def add_http_mock_response(code: HTTPStatus = HTTPStatus.OK):
        responses.add(
            responses.PUT,
            f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
            status=code,
        )

    @staticmethod
    def add_connectionerr_mock_response():
        responses.add(
            responses.PUT,
            f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
            body=requests.exceptions.ConnectionError(
                "<urllib3.connection.HTTPConnection object at 0x1080854c0>: "
                "Failed to establish a new connection: [Errno 8] "
                "nodename nor servname provided, or not known"
            ),
        )

    @staticmethod
    @responses.activate
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert result.stdout.startswith("Usage: pbench-results-push")
        assert not result.stderr

    @staticmethod
    @responses.activate
    def test_missing_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.CTRL_TEXT,
            ],
        )
        assert result.exit_code == 2
        assert result.stderr.find("Missing argument") > -1

    @staticmethod
    @responses.activate
    def test_bad_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.CTRL_TEXT,
                bad_tarball,
            ],
        )
        assert result.exit_code == 2
        assert (
            result.stderr.find(
                "Invalid value for 'RESULT_TB_NAME': "
                "File 'nothing.tar.xz' does not exist."
            )
            > -1
        )

    @staticmethod
    @responses.activate
    def test_extra_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.CTRL_TEXT,
                tarball,
                "extra-arg",
            ],
        )
        assert result.exit_code == 2
        assert result.stderr.find("unexpected extra argument") > -1

    @staticmethod
    @responses.activate
    def test_args():
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.add_http_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.CTRL_TEXT,
                tarball,
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert result.stderr == "File uploaded successfully\n"

    @staticmethod
    @responses.activate
    def test_token_prompt():
        """Test normal operation when the token option is omitted"""

        TestResultsPush.add_http_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[TestResultsPush.CTRL_TEXT, tarball],
            input=TestResultsPush.TOKN_TEXT + "\n",
        )
        assert result.exit_code == 0, result.stderr
        assert result.stderr == "File uploaded successfully\n"

    @staticmethod
    @responses.activate
    def test_token_envar(monkeypatch, caplog):
        """Test normal operation with the token in an environment variable"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_http_mock_response()
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[TestResultsPush.CTRL_TEXT, tarball])
        assert result.exit_code == 0, result.stderr
        assert result.stderr == "File uploaded successfully\n"

    @staticmethod
    @responses.activate
    def test_connection_error(monkeypatch, caplog):
        """Test handling of connection errors"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_connectionerr_mock_response()
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[TestResultsPush.CTRL_TEXT, tarball])
        assert result.exit_code == 1
        assert str(result.stderr).startswith("Cannot connect to")

    @staticmethod
    @responses.activate
    def test_http_error(monkeypatch, caplog):
        """Test handling of 404 errors"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_http_mock_response(HTTPStatus.NOT_FOUND)
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[TestResultsPush.CTRL_TEXT, tarball])
        assert result.exit_code == 1
        assert (
            str(result.stderr).find("Not Found") > -1
        ), f"stderr: {result.stderr!r}; stdout: {result.stdout!r}"
