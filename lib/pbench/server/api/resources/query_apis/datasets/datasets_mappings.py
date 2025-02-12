from http import HTTPStatus
from logging import Logger

from flask import jsonify
from flask.wrappers import Request, Response

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    APIAbort,
    ApiBase,
    ApiParams,
    ApiSchema,
    ParamType,
    Parameter,
    Schema,
)

from pbench.server.api.resources.query_apis.datasets import IndexMapBase
from pbench.server.database.models.template import TemplateNotFound


class DatasetsMappings(ApiBase):
    """
    Get properties of a document on which the client can search.
    This API currently only supports mapping properties of documents specified
    in RunIdBase.ES_INTERNAL_INDEX_NAMES.

    Example: get /api/v1/datasets/mappings/search
    :return:
    {
        "@metadata":
            [
                "controller_dir",
                "file-date",
                "file-name",
                "file-size",
                "md5",
                ...
            ],
       "host_tools_info":
            [
                "hostname",
                "hostname-f",
                ...
            ],
        "authorization":
            [
                "access",
                "owner"
            ]
        "run":
            [
                "id",
                "controller",
                "user",
                "name",
                ...
            ],
        "sosreports":
            [
                "hostname-f",
                "sosreport-error",
                "hostname-s",
                ...
            ]
    }
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter(
                        "dataset_view",
                        ParamType.KEYWORD,
                        required=True,
                        keywords=list(IndexMapBase.ES_INTERNAL_INDEX_NAMES.keys()),
                    )
                ),
                authorization=API_AUTHORIZATION.NONE,
            ),
        )

    def _get(self, params: ApiParams, request: Request) -> Response:
        """
        Return mapping properties of the document specified by the dataset view
        specified in the URI parameter (supported dataset views are defined in
        RunIdBase.ES_INTERNAL_INDEX_NAMES).

        For example, user can get the run document properties by making a GET
        request on datasets/mappings/search. Similarly other index documents
        can be fetched by making a GET request on appropriate dataset view
        names.

        The mappings are retrieved by querying the template database.
        """

        index = IndexMapBase.ES_INTERNAL_INDEX_NAMES[params.uri["dataset_view"]]
        try:
            mappings = IndexMapBase.get_mappings(index)
            result = {}
            for property in mappings["properties"]:
                if "properties" in mappings["properties"][property]:
                    result[property] = list(
                        mappings["properties"][property]["properties"].keys()
                    )

            # construct response object
            return jsonify(result)
        except TemplateNotFound as e:
            self.logger.exception(str(e))
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
