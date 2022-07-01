from abc import ABC, abstractmethod
from collections import defaultdict
import os

from requests import Session
from typing import Tuple
from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan

class PbenchCombinedData:
    """
    This Class serves as a container class for all pbench data collected
    from run indexes, result indexes, disk and host names, client names, and
    sosreports. 
    """
    def __init__(self, diagnostic_checks : dict()) -> None:
        """
        This initializes the self.data dictionary which will contain
        all the associated data mentioned above together. 
        It stores the diagnostic_checks passed in as an instance variable,
        so it has knowledge of what diagnostics to perform on incoming data. 
        It also has a self.diagnostics dict to store the results of the diagnostic
        checks performed - this is eventually added to the self.data dict.

        diagnostic_checks: Mapping of diagnostic_type (ie run, result, etc)
                       to list of concrete instances of the DiagnosticCheck
                       abstract class.
        """
        # FIXME: Keeping data and diagnostics separate for now, because might
        # want to increase generalizability for diagnostic specifications
        self.data = dict()
        self.diagnostics = {"run" : dict(), "result": dict(), 
                            "fio_extraction": dict(),
                            "client_side": dict()}
        self.diagnostic_checks = diagnostic_checks

    def data_check(self, doc, type : str) -> None:
        """
        This performs all the checks of the diagnostic type passed in
        on the doc passed in and updates the specific type's diagnostic
        data in self.diagnostics.
        doc: the data source passed in (could be run doc, result doc, etc)
        type: the diagnostic type (ie "run", "result", "fio_extraction", etc)
        """
        type_diagnostic = self.diagnostics[type]
        # if any of the checks fail, invalid is set to True
        invalid = False
        # create type_diagnostic data for all checks
        for check in self.diagnostic_checks[type]:
            check.diagnostic(doc)
            diagnostic_update, issue = check.get_vals()
            type_diagnostic.update(diagnostic_update)
            invalid |= issue

        # thus we can store whether this data added was valid or not
        type_diagnostic["valid"] = not invalid
    
    def add_run_data(self, doc) -> None:
        """
        Given a run doc, performs the specified diagnostic checks,
        stores the diagnostic data, and filters down the data to a
        desired subset and format. Filtered data stored in self.data
        doc: a run type document/data
        """
        run_diagnostic = self.diagnostics["run"]

        # should be checking existence
        run = doc["_source"] # TODO: Factor out into RunCheck1 
        run_id = run["@metadata"]["md5"] # TODO: Factor out into RunCheck1

        self.data_check(doc, "run")

        run_index = doc["_index"] # TODO: Factor out into RunCheck1

        # TODO: Figure out what exactly this sosreport section is doing,
        #       cuz I still don't know
        sosreports = dict()

        # NOTE: Only if run data valid (2 sosreports with non-different hosts)
        #       are the sosreports undergoing processing, else empty dict

        if run_diagnostic["valid"] == True:
            # FIXME: Should I remove the forloop here after the above change?
            for sosreport in run["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                    "inet": [nic["ipaddr"] for nic in sosreport["inet"]],
                    # FIXME: Key Error on inet6
                    # "inet6": [nic["ipaddr"] for nic in sosreport["inet6"]],
                }

        # TODO: This currently picks specific (possibly arbitrary) aspects
        #       of the initial run data to keep. SHould Factor this choice
        #       out to some function - Increase Generalizability/Extensibility
        self.data.update({
            "run_id": run_id,
            "run_index": run_index,
            "controller_dir": run["@metadata"]["controller_dir"],
            "sosreports": sosreports,
            # diagnostic data added here
            "diagnostics": self.diagnostics
        })
    
    def add_result_data(self, doc, result_diagnostic : dict) -> None:
        """
        Given a result doc, and its diagnostic data, updates the 
        internal store of the result diagnostic data, filters down
        and reformats result data and adds it to the existing run
        data in self.data
        doc: result type document/data
        result_diagnostic: dictionary from result diagnostic to value

        NOTE: result diagnostic checks need to be performed ahead of
              time in the PbenchCombinedDataCollection Object. This is
              because one check accounts for the case that a result data
              has no associated run. So we need to check that there is a
              valid run data associated before finding that data's
              PbenchCombinedData Object and adding the result to it. We
              also do this because even if record isn't valid and can't be
              added we still need to track the diagnostic info.
        """
        # sets result diagnostic data internally
        self.diagnostics["result"] = result_diagnostic
        # since this function will only be called on valid docs
        # because of a check in PbenchCombinedDataCollection we can just
        # udpate self.data directly

        # required data
        self.data.update(
            [
                ("iteration.name", doc["_source"]["iteration"]["name"]),
                ("sample.name", doc["_source"]["sample"]["name"]),
                ("run.name", doc["_source"]["run"]["name"]),
                ("benchmark.bs", doc["_source"]["benchmark"]["bs"]),
                ("benchmark.direct", doc["_source"]["benchmark"]["direct"]),
                ("benchmark.ioengine",doc["_source"]["benchmark"]["ioengine"]),
                ("benchmark.max_stddevpct", doc["_source"]["benchmark"]["max_stddevpct"]),
                ("benchmark.primary_metric", doc["_source"]["benchmark"]["primary_metric"]),
                ("benchmark.rw", self.sentence_setify(doc["_source"]["benchmark"]["rw"])),
                ("sample.client_hostname", doc["_source"]["sample"]["client_hostname"]),
                ("sample.measurement_type", doc["_source"]["sample"]["measurement_type"]),
                ("sample.measurement_title", doc["_source"]["sample"]["measurement_title"]),
                ("sample.measurement_idx", doc["_source"]["sample"]["measurement_idx"]),
                ("sample.mean", doc["_source"]["sample"]["mean"]),
                ("sample.stddev", doc["_source"]["sample"]["stddev"]),
                ("sample.stddevpct", doc["_source"]["sample"]["stddevpct"])
            ]
        )
    
        # optional workload parameters accounting for defaults if not found
        benchmark = doc["_source"]["benchmark"]
        self.data["benchmark.filename"] = self.sentence_setify(
            benchmark.get("filename", "/tmp/fio")
        )
        self.data["benchmark.iodepth"] = benchmark.get("iodepth", "32")
        self.data["benchmark.size"] = self.sentence_setify(benchmark.get("size", "4096M"))
        self.data["benchmark.numjobs"] = self.sentence_setify(benchmark.get("numjobs", "1"))
        self.data["benchmark.ramp_time"] = benchmark.get("ramp_time", "none")
        self.data["benchmark.runtime"] = benchmark.get("runtime", "none")
        self.data["benchmark.sync"] = benchmark.get("sync", "none")
        self.data["benchmark.time_based"] = benchmark.get("time_based", "none")

    def sentence_setify(self, sentence: str) -> str:
        """Splits input by ", " gets rid of duplicates and rejoins unique
        items into original format. Effectively removes duplicates in input.
        """
        return ", ".join(set([word.strip() for word in sentence.split(",")]))
    
    def extract_fio_result(self, incoming_url : str, session : Session) -> Tuple[list, list]:
        """
        Given an incoming_url it generates the specific url based on the data stored and performs
        diagnostic checks specified. If successful it attempts to get diskname and
        hostname data from the response object from the request sent to the url.
        incoming_url: pbench server url prefix to fetch unpacked data
        session: A session to make request to url
        returns: Tuple of list of disknames and list of hostnames
        """
        # TODO: Why is this the url required. Would this be different in any case?
        #       Does this need to be more general?
        url = (
            incoming_url
            + self.data["controller_dir"]
            + "/"
            + self.data["run.name"]
            + "/"
            + self.data["iteration.name"]
            + "/"
            + self.data["sample.name"]
            + "/"
            + "fio-result.txt"
        )

        # diagnostic checks of disk and host names (fio extraction)
        self.data_check(url, "fio_extraction")

        if self.diagnostics["fio_extraction"]["valid"] != True:
            # FIXME: are these results defaults we still want?
            disknames, hostnames = ([], [])
        else:
            response = session.get(url, allow_redirects=True)
            document = response.json()
            # from disk_util and client_stats get diskname and clientname info
            try:
                disk_util = document["disk_util"]
            except KeyError:
                disknames = []
            else:
                disknames = [disk["name"] for disk in disk_util if "name" in disk]

            try:
                client_stats = document["client_stats"]
            except KeyError:
                hostnames = []
            else:
                hostnames = list(
                    set([host["hostname"] for host in client_stats if "hostname" in host])
                )

        return (disknames, hostnames)
    
    def add_host_and_disk_names(self, diskhost_map : dict, incoming_url : str, session: Session) -> None:
        """
        Adds the disk and host names to the self.data dict.
        incoming_url: pbench server url prefix to fetch unpacked data
        session: A session to make request to url
        diskhost_map: maps run id and iteration name to disk and host names
        """
        # combination of run_id and iteration.name used as key for diskhost_map
        key = f"{self.data['run_id']}/{self.data['iteration.name']}"
        # if not in map finds it using extract_fio_result and adds it to dict
        # (because disk and host names associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation)
        if key not in diskhost_map:
            disknames, hostnames = self.extract_fio_result(incoming_url, session)
            diskhost_map[key] = (disknames, hostnames)
        disknames, hostnames = diskhost_map[key]
        # updates self.data with disk and host names
        self.data.update(
            [
                ("disknames", disknames),
                ("hostnames", hostnames)
            ]
        )
    
    def extract_clients(self, es : Elasticsearch) -> list[str]:
        """
        Given that self.data already contains the run and
        result data, this function finds and returns a list
        of unique raw client names.
        es: Elasticsearch object
        returns: list of unique raw client names
        """
        # TODO: Need to determine how specific this part is and
        #       whether it can be different or more general
        run_index = self.data["run_index"]
        parent_id = self.data["run_id"]
        iter_name = self.data["iteration.name"]
        sample_name = self.data["sample.name"]
        parent_dir_name = f"/{iter_name}/{sample_name}/clients"
        query = {
            "query": {
                "query_string": {
                    "query": f'_parent:"{parent_id}"'
                    f' AND ancestor_path_elements:"{iter_name}"'
                    f' AND ancestor_path_elements:"{sample_name}"'
                    f" AND ancestor_path_elements:clients"
                }
            }
        }

        client_names_raw = []
        for doc in scan(
            es,
            query=query,
            index=run_index,
            doc_type="pbench-run-toc-entry",
            scroll="1m",
            request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
        ):
            src = doc["_source"]
            if src["parent"] == parent_dir_name:
                client_names_raw.append(src["name"])
        # FIXME: if we have an empty list, do we still want to use those results?
        return list(set(client_names_raw))

    def add_client_names(self, clientnames_map : dict, es : Elasticsearch) -> None:
        """
        This adds the associated clientnames to self.data only if
        it passes the checks specified
        clientnames_map: map from run_id to list of client names
        es: Elasticsearch object where data is stored
        """
        key = self.data["run_id"]
        # if we haven't seen this run_id before, extract client names
        # and add it to map (because clients associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation) 
        if key not in clientnames_map:
            client_names = self.extract_clients(es)
            clientnames_map[key] = client_names
        client_names = clientnames_map[key]

        self.data_check(client_names, "client_side")
        if self.data["diagnostics"]["client_side"]["valid"] == True:
            self.data["clientnames"] = client_names

class PbenchCombinedDataCollection:
    def __init__(self, incoming_url, session, es):
        self.run_id_to_data_valid = dict()
        self.invalid = {"run": dict(), "result": dict(), "client_side": dict()}
        # not sure if this is really required but will follow current
        # implementation for now
        self.results_seen = dict()
        self.es = es
        self.incoming_url = incoming_url
        self.session = session
        self.trackers = {"run": dict(), "result": dict(), "fio_extraction": dict(), "client_side": dict()}
        self.diagnostic_checks = {"run": [ControllerDirRunCheck(), SosreportRunCheck()],
                                    # TODO: need to fix order of these result checks to match the original      
                                    "result": [SeenResultCheck(self.results_seen), BaseResultCheck(),
                                                RunNotInDataResultCheck(self.run_id_to_data_valid),
                                                ClientHostAggregateResultCheck()],
                                    "fio_extraction": [FioExtractionCheck(self.session)],
                                    "client_side": [ClientNamesCheck()]}
        self.trackers_initialization()
        self.result_temp_id = 0
        self.diskhost_map = dict()
        self.clientnames_map = dict()
    
    def __str__(self):
        return str("---------------\n" +
            # "Valid Data: \n" +
            # str(self.run_id_to_data_valid) + "\n" +
            # "Results Seen: \n" +
            # str(self.results_seen) + "\n" +
            # "Results Seen: " + str(len(self.results_seen)) + "\n" +
            # "Diagnostic Checks Used: \n" + str(self.diagnostic_checks) + "\n" +
            "Trackers: \n" +
            str(self.trackers))
    
    def trackers_initialization(self):
        for type in self.diagnostic_checks:
            self.trackers[type]["valid"] = 0
            self.trackers[type]["total_records"] = 0
            for check in self.diagnostic_checks[type]:
                for name in check.diagnostic_names:
                    self.trackers[type].update({name: 0})

    def update_diagnostic_trackers(self, diagnsotic_data : dict, type : str):
        # allowed types: "run", "result"
        # type_diagnostic = record.data["diagnostics"][type]
        # update trackers based on run_diagnostic data collected
        self.trackers[type]["total_records"] += 1
        for diagnostic in diagnsotic_data:
            if diagnsotic_data[diagnostic] == True:
                self.trackers[type][diagnostic] += 1
                
        
    def print_stats(self):
        stats = "Pbench runs Stats: \n"
        for tracker in self.trackers["run"]:
            stats += f"{tracker}: {self.trackers['run'][tracker] : n} \n"

        print(stats, flush=True)
    
    def add_run(self, doc):
        new_run = PbenchCombinedData(self.diagnostic_checks)
        new_run.add_run_data(doc)
        self.update_diagnostic_trackers(new_run.data["diagnostics"]["run"], "run")
        run_id = new_run.data["run_id"]
        if new_run.data["diagnostics"]["run"]["valid"] == True:
            self.run_id_to_data_valid[run_id] = new_run
        else:
            self.invalid["run"][run_id] = new_run

    def result_screening_check(self, doc):
        result_diagnostic = dict()
        invalid = False

        # create run_diagnostic data for all checks
        for check in self.diagnostic_checks["result"]:
            check.diagnostic(doc)
            diagnostic_update, issue = check.get_vals()
            result_diagnostic.update(diagnostic_update)
            invalid |= issue
        
        result_diagnostic["valid"] = not invalid
        return result_diagnostic
    
    def add_result(self, doc):
        result_diagnostic_return = self.result_screening_check(doc)
        self.update_diagnostic_trackers(result_diagnostic_return, "result")
        if result_diagnostic_return["valid"] == True:
            associated_run_id = doc["_source"]["run"]["id"]
            associated_run = self.run_id_to_data_valid[associated_run_id]
            associated_run.add_result_data(doc, result_diagnostic_return)
            associated_run.add_host_and_disk_names(self.diskhost_map, self.incoming_url, self.session)
            self.update_diagnostic_trackers(associated_run.data["diagnostics"]["fio_extraction"], "fio_extraction")
            associated_run.add_client_names(self.clientnames_map, self.es)
            self.update_diagnostic_trackers(associated_run.data["diagnostics"]["client_side"], "client_side")
            # if associated_run.data["diagnostics"]["client_side"]["valid"] == False:
                # associated_run = self.run_id_to_data_valid.pop(associated_run_id)
                # self.invalid["client_side"][associated_run_id] = associated_run
                # self.trackers["result"]["valid"] -= 1
        else:
            doc.update({"diagnostics": {"result" : result_diagnostic_return}})
            if result_diagnostic_return["missing._id"] == False:
                self.invalid["result"][result_diagnostic_return["missing._id"]] = doc
            else:
                self.invalid["result"]["missing_so_temo_id_" + str(self.result_temp_id)] = doc
                self.result_temp_id += 1
    
    def get_runs(self):
        return self.run_id_to_data_valid

 
class DiagnosticCheck(ABC):

    def __init__(self):
        self.initialize_properties()
    
    @property
    @abstractmethod
    def diagnostic_names(self):
        "Define me!"
        pass
 
    # appropriately updates instance variables 
    @abstractmethod
    def diagnostic(self, doc):
        self.initialize_properties()
    
    def initialize_properties(self):
        self.diagnostic_return = defaultdict(self.default_value)
        self.issues = False
        for tracker in self.diagnostic_names:
            self.diagnostic_return[tracker]
    
    def default_value(self):
        return False

    def get_vals(self):
        return self.diagnostic_return, self.issues
    

class ControllerDirRunCheck(DiagnosticCheck):

    _diagnostic_names = ["missing_ctrl_dir"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if "controller_dir" not in doc["_source"]["@metadata"]:
            self.diagnostic_return["missing_ctrl_dir"] = True
            self.issues = True

class SosreportRunCheck(DiagnosticCheck):

    _diagnostic_names = ["missing_sosreports", 
        "non_2_sosreports", "sosreports_diff_hosts"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        # check if sosreports present
        if "sosreports" not in doc["_source"]:
            self.diagnostic_return["missing_sosreports"] = True
            self.issues = True
        
        # check if run has exactly 2 sosreports
        elif len(doc["_source"]["sosreports"]) != 2:
            self.diagnostic_return["non_2_sosreports"] = True
            self.issues = True
        
        else:
            # check if 2 sosreports have different hosts
            first = doc["_source"]["sosreports"][0]
            second = doc["_source"]["sosreports"][1]
            if first["hostname-f"] != second["hostname-f"]:
                self.diagnostic_return["sosreports_diff_hosts"] = True
                self.issues = True     

class SeenResultCheck(DiagnosticCheck):

    def __init__(self, results_seen : dict):
        self.results_seen = results_seen

    _diagnostic_names = ["missing._id", "duplicate_result_id"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names
    
    def diagnostic(self, doc):
        super().diagnostic(doc)
        # first check if result doc has a result id field
        if "_id" not in doc:
            self.diagnostic_return["missing._id"] = True
            self.issues = True
        else:
            result_id = doc["_id"]
            
            # second check if result has been seen already
            # NOTE: not sure if this check is really necessary (whether
            # a case where duplicate results occur exists)
            if result_id in self.results_seen:
                self.diagnostic_return["duplicate_result_id"] = True
                self.issues = True
            else:
                self.results_seen[result_id] = True

class BaseResultCheck(DiagnosticCheck):

    # format missing.property/subproperty/...
    _diagnostic_names = [
        "missing._source",
        "missing._source/run",
        "missing._source/run/id",
        "missing._source/run/name",
        "missing._source/iteration",
        "missing._source/iteration/name",
        "missing._source/sample",
        "missing._source/sample/name",
        "missing._source/sample/measurement_type",
        "missing._source/sample/measurement_title",
        "missing._source/sample/measurement_idx",
        "missing._source/sample/mean",
        "missing._source/sample/stddev",
        "missing._source/sample/stddevpct",
        "missing._source/sample/client_hostname",
        "missing._source/benchmark/bs",
        "missing._source/benchmark/direct",
        "missing._source/benchmark/ioengine",
        "missing._source/benchmark/max_stddevpct",
        "missing._source/benchmark/primary_metric",
        "missing._source/benchmark/rw",
    ]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        
        self.issues = True
        # unforunately very ugly if statement to check what
        # fields are missing to create comprehensive diagnostic info
        if "_source" not in doc:
            self.diagnostic_return["missing._source"] = True 
        elif "run" not in doc["_source"]:
            self.diagnostic_return["missing._source/run"] = True
        elif "id" not in doc["_source"]["run"]:
            self.diagnostic_return["missing._source/run/id"] = True
        elif "name" not in doc["_source"]["run"]:
            self.diagnostic_return["missing._source/run/name"] = True
        elif "iteration" not in doc["_source"]:
            self.diagnostic_return["missing._source/iteration"] = True
        elif "name" not in doc["_source"]["iteration"]:
            self.diagnostic_return["missing._source/iteration/name"] = True
        elif "sample" not in doc["_source"]:
            self.diagnostic_return["missing._source/sample"] = True
        elif "name" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/name"] = True
        elif "measurement_type" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_type"] = True
        elif "measurement_title" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_title"] = True
        elif "measurement_idx" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_idx"] = True
        elif "mean" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/mean"] = True
        elif "stddev" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/stddev"] = True
        elif "stddevpct" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/stddevpct"] = True
        elif "client_hostname" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/client_hostname"] = True
        elif "benchmark" not in doc["_source"]:
            self.diagnostic_return["missing._source/benchmark"] = True
        elif "bs" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/bs"] = True
        elif "direct" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/direct"] = True
        elif "ioengine" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/ioengine"] = True
        elif "max_stddevpct" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/max_stddevpct"] = True
        elif "primary_metric" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/primary_metric"] = True
        elif "rw" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/rw"] = True
        else:
            self.issues = False


class RunNotInDataResultCheck(DiagnosticCheck):

    def __init__(self, pbench_combined_data : PbenchCombinedDataCollection):
        self.pbench_combined_data = pbench_combined_data

    _diagnostic_names = ["run_not_in_data"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if doc["_source"]["run"]["id"] not in self.pbench_combined_data:
            self.diagnostic_return["run_not_in_data"] = True
            self.issues = True

class ClientHostAggregateResultCheck(DiagnosticCheck):
    # aggregate_result not sure what this is checking
    _diagnostic_names = ["client_hostname_all"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if doc["_source"]["sample"]["client_hostname"] == "all":
            self.diagnostic_return["client_hostname_all"] = True
            self.issues = True


class FioExtractionCheck(DiagnosticCheck):

    def __init__(self, session):
        self.session = session
        # FIXME: are these results we still want in failure cases?
        self.disk_host_names = ([],[])

    _diagnostic_names = ["session_response_unsuccessful",
                        "response_invalid_json"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        #doc acting as url
        super().diagnostic(doc)
        
        # check if the page is accessible
        response = self.session.get(doc, allow_redirects=True)
        if response.status_code != 200:  # successful
            self.diagnostic_return["session_response_unsuccessful"] = True
            self.issues = True
        else:
            try:
                response.json() 
            except ValueError:
                self.diagnostic_return["response_invalid_json"] = True
                self.issues = True
        
class ClientNamesCheck(DiagnosticCheck):

    _diagnostic_names = ["0_clients",
                        "2_or_more_clients"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        #doc acting as clientnames
        super().diagnostic(doc)
        
        # Ignore result if 0 or more than 1 client names
        if not doc:
            self.diagnostic_return["0_clients"] = True
            self.issues = True
        elif len(doc) > 1:
            self.diagnostic_return["2_or_more_clients"] = True
            self.issues = True
        else:
            pass
            
# TODO: There should be a way to specify the data source and the
#       fields/properties desired from that source, and the data
#       sources are filtered down as desired. And it autogenerates
#       the checks to perform. - Generability/Extensibility