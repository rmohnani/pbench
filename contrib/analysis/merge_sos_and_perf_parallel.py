#!/usr/bin/env python3

import argparse

import multiprocessing
import requests
import time
import json

from datetime import datetime
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from pbench_combined_data import ComplexEncoder, PbenchCombinedDataCollection

from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan


def _month_gen(now: datetime):
    """Generate YYYY-MM stings from all the months, inclusively, between the
    given start and end dates.
    """
    start = now - relativedelta(years=1)
    first_month = start.replace(day=1)
    last_month = now + relativedelta(day=31)
    for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
        yield f"{m.year:04}-{m.month:02}"


def merge_run_result_index(
    es: Elasticsearch,
    month: str,
    record_limit: int,
    pbench_data: PbenchCombinedDataCollection,
) -> None:
    """Merges all run and result data for a given month and stores it inside pbench_data.

    Given a month, gets the run_index and result_index names for the month specified.
    Loops over every doc in the run_index that is of type 'pbench-run', and
    adds it to pbench_data. Checks if valid record_limit is met and stops
    going through more run data. Then loops over all result docs in the month
    of type 'pbench-result-data-sample' and adds it to pbench_data.

    #NOTE: Need to still go through all result data for the month to ensure we
           retrive all result data associated with the runs added, since we
           don't know more specifically the associations within the index, this
           is the best we can do so far.

    #NOTE: Since only within months do the processing of run and result need to
           be sequential, we can process multiple months in parallel,
           hopefully reducing time taken overall.

    Parameters
    ----------
    es : Elasticsearch
        Elasticsearch object where data is stored
    month : str
        Month Year string stored in YYYY-MM format
    record_limit : int
        Number of valid run records desired.
        Serves as termination check.
    pbench_data : PbenchCombinedDataCollection
        Store for all the processed pbench data and diagnostic
        and tracking information.

    Returns
    -------
    None

    """
    run_index = f"dsa-pbench.v4.run.{month}"
    result_index = f"dsa-pbench.v4.result-data.{month}-*"

    for run_doc in es_data_gen(es, run_index, "pbench-run"):
        pbench_data.add_run(run_doc)
        if record_limit != -1:
            if pbench_data.trackers["run"]["valid"] >= record_limit:
                break

    for result_doc in es_data_gen(es, result_index, "pbench-result-data-sample"):
        pbench_data.add_result(result_doc)

def merge_run_result_mp(es: Elasticsearch, month: str, record_limit: int, incoming_url : str, session : requests.Session):

    pbench_data = PbenchCombinedDataCollection(incoming_url, session, es)

    run_index = f"dsa-pbench.v4.run.{month}"
    result_index = f"dsa-pbench.v4.result-data.{month}-*"

    for run_doc in es_data_gen(es, run_index, "pbench-run"):
        pbench_data.add_run(run_doc)
        if record_limit != -1:
            if pbench_data.trackers["run"]["valid"] >= record_limit:
                break

    for result_doc in es_data_gen(es, result_index, "pbench-result-data-sample"):
        pbench_data.add_result(result_doc)
    
    # return json.dumps(pbench_data.to_json(), cls=ComplexEncoder)
    return None

def merge_non_serializable(run_doc_generator, result_doc_generator, record_limit):

    pbench_data = PbenchCombinedDataCollection()

    for run_doc in run_doc_generator:
        pbench_data.add_run(run_doc)
        if record_limit != -1:
            if pbench_data.trackers["run"]["valid"] >= record_limit:
                break
    
    for result_doc in result_doc_generator:
        pbench_data.add_result(result_doc)
    
    return pbench_data


def es_data_gen(es: Elasticsearch, index: str, doc_type: str):
    """Yield documents where the `run.script` field is "fio" for the given index
    and document type.

    Parameters
    ----------
    es : Elasticsearch
        Elasticsearch object where data is stored
    index : str
        index name
    doc_type : str
        document type

    Yields
    -------
    doc : json
        json data representing doc and its contents

    """
    query = {"query": {"query_string": {"query": "run.script:fio"}}}

    for doc in scan(
        es,
        query=query,
        index=index,
        doc_type=doc_type,
        scroll="1d",
        request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
    ):
        yield doc


def merge_data(month1: str, month2: str, es : Elasticsearch, record_limit : int, incoming_url : str, session : requests.Session):
    month1_data = PbenchCombinedDataCollection()
    month2_data = PbenchCombinedDataCollection()
    merge_run_result_index(es, month1, record_limit, month1_data)
    merge_run_result_index(es, month2, record_limit, month2_data)
    print(month1_data)
    print(month2_data)
    # month1_data.print_stats()
    # month2_data.print_stats()
    month1_data.combine_data(month2_data)
    print(month1_data)
    # month1_data.print_stats()
    # month1_data.print_json()
    # print(month1_data.__dict__)

def args_generator(months, es, record_limit):
    args_to_pass = []
    for month in months:
        run_index = f"dsa-pbench.v4.run.{month}"
        result_index = f"dsa-pbench.v4.result-data.{month}-*"
        run_docs = [run for run in es_data_gen(es, run_index, "pbench-run")]
        result_docs = [result for result in es_data_gen(es, result_index, "pbench-result-data-sample")]
        args_to_pass.append((run_docs, result_docs, record_limit))
    return args_to_pass
        

def main(args):

    # URL prefix to fetch unpacked data
    incoming_url = f"{args.url_prefix}/incoming/"

    if args.profile_memory_usage:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    ncpus = multiprocessing.cpu_count() - 1 if args.cpu_n == 0 else args.cpu_n
    pool = multiprocessing.Pool(ncpus) if ncpus != 1 else None

    es = Elasticsearch(
        [f"{args.es_host}:{args.es_port}"], timeout=60
    )  # to prevent read timeout errors (60 is arbitrary)

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})
    # pbench_data = PbenchCombinedDataCollection(incoming_url, session, es)

    scan_start = time.time()
    now = datetime.utcfromtimestamp(scan_start)

    # Non-serializable version try:

    # results = pool.starmap(merge_non_serializable, 
    #     [([item for item in es_data_gen(es, f"dsa-pbench.v4.run.{month}", "pbench-run")],
    #        [item for item in es_data_gen(es, f"dsa-pbench.v4.result-data.{month}-*", "pbench-result-data-sample")],
    #        args.record_limit) for month in _month_gen(now)])

    # Non serializable try with 2 months:

    # ["2021-07", "2021-08"]
    # [month for month in _month_gen(now)]
    months = ["2021-07", "2021-08", "2021-09", "2021-10", "2021-11", "2021-12", "2022-01", "2022-02"]
    results = pool.starmap(merge_non_serializable, args_generator(months, es, args.record_limit))
    for result in results:
        print(result)


    # forcing serializing and deseralizing of object which will probably take a lot of time.
    # seems unnecessary so I want to find a better way
    # THis broken can't return object from function, need to return string or int. So ideally dump object into json
    # string format and load it in afterwards. 
    # results = pool.starmap(merge_run_result_mp, [(es, month, args.record_limit, incoming_url, session) for month in _month_gen(now)])
    # for result in results:
    #     result.print_stats()
    #     pbench_data.combine_data(result)
    #     if args.record_limit != -1:
    #         if len(pbench_data.run_id_to_data_valid) >= args.record_limit:
    #             break

    # TODO: This doesn't work because modifying class attributes. Need to figure out work around
    #       and see if ideally we could do this processing on the cloud somehow.
    # pool.starmap(merge_run_result_index, [(es, month, args.record_limit, pbench_data) for month in _month_gen(now)])

    # for month in _month_gen(now):
    #     merge_run_result_index(es, month, args.record_limit, pbench_data)
        # if args.record_limit != -1:
        #     if len(pbench_data.run_id_to_data_valid) >= args.record_limit:
        #         break

    # merge_data("2021-07", "2021-08", es, args.record_limit, incoming_url, session)
    # merge_data("2021-09", "2021-10", es, args.record_limit, incoming_url, session)

    # Parallel mergin



    # NOTE: Not writing sosreports and results to files. Will work on this step
    #       of sosreport processing, etc next.

    # with open("sosreport_fio.txt", "w") as log, open("pbench_fio.json", "w") as outfile:
    #     generator = process_results(
    #         es, now, session, incoming_url, pool, pbench_runs, stats
    #     )
    #     for result in generator:
    #         print(result)
    #         print("\n")
    #         result_cnt += 1
    #         for sos in result["sosreports"].keys():
    #             log.write("{}\n".format(sos))
    #         log.flush()
    #         outfile.write(json.dumps(result))
    #         outfile.write("\n")
    #         outfile.flush()

    scan_end = time.time()
    duration = scan_end - scan_start

    # pbench_data.print_stats()
    print(f"--- merging run and result data took {duration:0.2f} seconds", flush=True)

    if memprof:
        print(
            f"Final memory profile ... {memprof.heap()}",
            flush=True,
        )

    return 0


def parse_arguments() -> argparse.Namespace:
    """Specifies Command Line argument parsing.

    Gives help info when running this file as to what arguments needed, etc.
    Adds optional flags to change execution of code.

    Returns
    -------
    args : argparse.Namespace
        arguments passed in stored with easily accessible
        variable names

    """
    parser = argparse.ArgumentParser(description="Host and Server Information")
    parser.add_argument(
        "es_host", action="store", type=str, help="Elasticsearch host name"
    )
    parser.add_argument(
        "es_port", action="store", type=int, help="Elasticsearch port number"
    )
    parser.add_argument(
        "url_prefix",
        action="store",
        type=str,
        help="Pbench server url prefix to extract host and disk names",
    )
    # parser.add_argument("sosreport_host_server", action="store" ,dest="sos_host", type=str, help="Sosreport host server to access sosreport info")
    parser.add_argument(
        "--cpu",
        action="store",
        dest="cpu_n",
        type=int,
        default=1,
        help="Number of CPUs to be used",
    )
    parser.add_argument(
        "--limit",
        action="store",
        dest="record_limit",
        type=int,
        default=-1,
        help="Number of desired acceptable results for processing",
    )
    # TODO: need to figure out how to allow both limiting and non-limiting options with argparse. But suppose would never want to limit in real use case.
    # Temporarily used -1 as default and it meaning all
    parser.add_argument(
        "--profile",
        action="store_true",
        dest="profile_memory_usage",
        help="Want memory usage profile",
    )
    args = parser.parse_args()
    return args


# point of entry
if __name__ == "__main__":
    args = parse_arguments()
    status = main(args)
