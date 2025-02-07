import logging
from typing import Dict, List, Tuple
from urllib.parse import urlencode, urlparse

from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy.orm import Query

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    ApiBase,
    ApiParams,
    ApiSchema,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError


class DatasetsList(ApiBase):
    """
    API class to list datasets based on PostgreSQL metadata
    """

    def __init__(self, config: PbenchServerConfig, logger: logging.Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                query_schema=Schema(
                    Parameter("name", ParamType.STRING),
                    Parameter("owner", ParamType.USER),
                    Parameter("access", ParamType.ACCESS),
                    Parameter("start", ParamType.DATE),
                    Parameter("end", ParamType.DATE),
                    Parameter("offset", ParamType.INT),
                    Parameter("limit", ParamType.INT),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=Metadata.METADATA_KEYS,
                        key_path=True,
                        string_list=",",
                    ),
                ),
                authorization=API_AUTHORIZATION.USER_ACCESS,
            ),
        )

    def get_paginated_obj(
        self, query: Query, json: JSON, url: str
    ) -> Tuple[List, Dict[str, str]]:
        """
        Helper function to return a slice of datasets (constructed according to the
        user specified limit and an offset number) and a paginated object containing next page
        url and total items count.

        E.g. specifying the following limit and offset values will result in the corresponding
        dataset slice:
        "limit": 10, "offset": 20 -> dataset[20: 30]
        "limit": 10 -> dataset[0: 10]
        "offset": 20 -> dataset[20: total_items_count]

        TODO: We may need to optimize the pagination
            e.g Use of unique pointers to record the last returned row and then use
            this pointer in subsequent page request instead of an initial start to
            narrow down the result.
        """
        paginated_result = {}
        total_count = query.count()
        query = query.order_by(Dataset.name)

        # Shift the query search by user specified offset value,
        # otherwise return the batch of results starting from the
        # first queried item.
        offset = json.get("offset", 0)
        query = query.offset(offset)

        # Get the user specified limit, otherwise return all the items
        limit = json.get("limit")
        if limit:
            query = query.limit(limit)

        items = query.all()

        next_offset = offset + len(items)
        if next_offset < total_count:
            json["offset"] = next_offset
            parsed_url = urlparse(url)
            next_url = parsed_url._replace(query=urlencode(json)).geturl()
        else:
            next_url = ""

        paginated_result["next_url"] = next_url
        paginated_result["total"] = total_count
        return items, paginated_result

    def _get(self, params: ApiParams, request: Request) -> Response:
        """
        Get a list of datasets matching a set of criteria.

        NOTE: This does not rely on a JSON payload to identify the dataset and
        desired metadata keys; instead we rely on URI query parameters.

        Args:
            params: API parameters
            request: The original Request object

        GET /api/v1/datasets/list?start=1970-01-01&end=2040-12-31&owner=fred&metadata=dashboard.seen,server.deletion
        """
        json = params.query

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(Dataset)
        if "start" in json and "end" in json:
            self.logger.info("Adding start / end query")
            query = query.filter(Dataset.created.between(json["start"], json["end"]))
        elif "start" in json:
            self.logger.info("Adding start query")
            query = query.filter(Dataset.created >= json["start"])
        elif "end" in json:
            self.logger.info("Adding end query")
            query = query.filter(Dataset.created <= json["end"])
        if "name" in json:
            self.logger.info("Adding name query")
            query = query.filter(Dataset.name.contains(json["name"]))
        query = self._build_sql_query(json.get("owner"), json.get("access"), query)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "QUERY {}",
                query.statement.compile(compile_kwargs={"literal_binds": True}),
            )

        # Execute the filtered query, sorted by dataset name so we have a
        # consistent and reproducible output to compare.
        datasets, paginated_result = self.get_paginated_obj(
            query=query, json=json, url=request.url
        )

        keys = json.get("metadata")

        response = []
        for dataset in datasets:
            d = {
                "name": dataset.name,
                "run_id": dataset.md5,
            }
            try:
                d["metadata"] = self._get_dataset_metadata(dataset, keys)
            except MetadataError as e:
                self.logger.warning(
                    "Error getting metadata {} for dataset {}: {}", keys, dataset, e
                )
            response.append(d)

        paginated_result["results"] = response
        return jsonify(paginated_result)
