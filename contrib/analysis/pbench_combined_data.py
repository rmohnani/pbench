from abc import ABC, abstractmethod
from collections import defaultdict
import os

class PbenchCombinedData:
    def __init__(self, diagnostic_checks):
        self.data = dict()
        self.diagnostics = {"run" : dict(), "result": dict()}
        self.diagnostic_checks = diagnostic_checks
    
    def add_run_data(self, doc):
        run_diagnostic = self.diagnostics["run"]

        run = doc["_source"]
        run_id = run["@metadata"]["md5"]

        invalid = False
        # create run_diagnostic data for all checks
        for check in self.diagnostic_checks["run"]:
            this_check = check()
            this_check.diagnostic(doc)
            diagnostic_update, issue = this_check.get_vals()
            run_diagnostic.update(diagnostic_update)
            invalid |= issue

        run_diagnostic["valid"] = not invalid

        run_index = doc["_index"]

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

        self.data.update({
            "run_id": run_id,
            "run_index": run_index,
            "controller_dir": run["@metadata"]["controller_dir"],
            "sosreports": sosreports,
            "diagnostics": self.diagnostics
        })

        print(self.data)
    
    def add_result_data(self, doc, results_seen, all_data):
        self.transform_result(doc, results_seen, all_data)
    
    def transform_result(self, doc, results_seen, all_data):

        # Diagnostic checks and data collection
        result_diagnostic = self.diagnostics["result"]
        invalid = False
        # NOTE: These checks can't be put into loop in current form
        # because ordering and different requirements of params
        # first check result not already seen before
        first_result_check = SeenResultCheck()
        first_result_check.diagnostic(doc, results_seen)
        diagnostic_update1, issues1 = first_result_check.get_vals()
        result_diagnostic.update(diagnostic_update1)
        invalid |= issues1

        # second check for all required fields/properties existence
        second_result_check = BaseResultCheck()
        second_result_check.diagnostic(doc)
        diagnostic_update2, issues2 = second_result_check.get_vals()
        result_diagnostic.update(diagnostic_update2)
        invalid |= issues2

        # third check if runs are missing
        third_result_check = RunNotInDataResultCheck(all_data)
        third_result_check.diagnostic(doc)
        diagnostic_update3, issues3 = third_result_check.get_vals()
        result_diagnostic.update(diagnostic_update3)
        invalid |= issues3

        # fourth check if runs are missing
        fourth_result_check = ClientHostAggregateResultCheck()
        fourth_result_check.diagnostic(doc)
        diagnostic_update4, issues4 = fourth_result_check.get_vals()
        result_diagnostic.update(diagnostic_update4)
        invalid |= issues4

        result_diagnostic["valid"] = not invalid











        
        

class PbenchCombinedDataCollection:
    def __init__(self):
        self.run_id_to_data_valid = dict()
        self.invalid = dict()
        self.trackers = {"run": dict(), "result": dict()}
        self.diagnostic_checks = {"run": [ControllerDirRunCheck, SosreportRunCheck],
                                    "result": []}
        self.trackers_initialization()
        # not sure if this is really required but will follow current
        # implementation for now
        self.results_seen = dict()

    
    def trackers_initialization(self):
        for type in self.diagnostic_checks:
            self.trackers[type]["valid"] = 0
            self.trackers[type]["total_records"] = 0
            for check in self.diagnostic_checks[type]:
                check_instance = check()
                for name in check_instance.diagnostic_names:
                    self.trackers[type].update({name: 0})

    def update_run_diagnostic_trackers(self, record : PbenchCombinedData):
        run_diagnostic = record.data["diagnostics"]["run"]
        # update trackers based on run_diagnostic data collected
        self.trackers["run"]['total_records'] += 1
        for diagnostic in run_diagnostic:
            if run_diagnostic[diagnostic] == True:
                self.trackers["run"][diagnostic] += 1
        
    def print_stats(self):
        stats = "Pbench runs Stats: \n"
        for tracker in self.trackers["run"]:
            stats += f"{tracker}: {self.trackers['run'][tracker] : n} \n"

        print(stats, flush=True)
    
    def add_run(self, doc):
        new_run = PbenchCombinedData(self.diagnostic_checks)
        new_run.add_run_data(doc)
        self.update_run_diagnostic_trackers(new_run)
        run_id = new_run.data["run_id"]
        if new_run.data["diagnostics"]["run"]["valid"] == True:
            self.run_id_to_data_valid[run_id] = new_run
        else:
            self.invalid[run_id] = new_run

    
    def get_runs(self):
        return self.run_id_to_data_valid

 
class DiagnosticCheck(ABC):

    def __init__(self):
        self.diagnostic_return = defaultdict(self.default_value)
        self.issues = False
        self.initialize_diagnostic_return(self.diagnostic_names)
    
    @property
    @abstractmethod
    def diagnostic_names(self):
        "Define me!"
        pass
 
    # appropriately updates instance variables 
    @staticmethod
    @abstractmethod
    def diagnostic(self, doc):
        ...
    
    def default_value(self):
        return False

    def initialize_diagnostic_return(self, tracker_list):
        for tracker in tracker_list:
            self.diagnostic_return[tracker]

    def get_vals(self):
        return self.diagnostic_return, self.issues

class ControllerDirRunCheck(DiagnosticCheck):

    _diagnostic_names = ["missing_ctrl_dir"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
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

    _diagnostic_names = ["missing._id", "duplicate_result_id"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names
    
    def diagnostic(self, doc, results_seen):

        # first check if result doc has a result id field
        if "_id" not in doc:
            self.diagnostic_return["missing._id"] = True
            self.issues = True
        else:
            result_id = doc["_id"]
            
            # second check if result has been seen already
            # NOTE: not sure if this check is really necessary (whether
            # a case where duplicate results occur exists)
            if result_id in results_seen:
                self.diagnostic_return["duplicate_result_id"] = True
                self.issues = True
            else:
                results_seen[result_id] = True

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
        if doc["_source"]["run"]["id"] not in self.pbench_combined_data:
            self.diagnostic_return["run_not_in_data"] = True
            self.issues = True

# class MeanNotInSampleResultCheck(DiagnosticCheck):

#     _diagnostic_names = ["mean_not_in_sample"]

#     @property
#     def diagnostic_names(self):
#         return self._diagnostic_names

#     def diagnostic(self, doc):
#         if "mean" not in doc["_source"]["sample"]:
#             self.diagnostic_return["mean_not_in_sample"] = True
#             self.issues = True

class ClientHostAggregateResultCheck(DiagnosticCheck):
    # aggregate_result not sure what this is checking
    _diagnostic_names = ["client_hostname_all"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        if doc["_source"]["sample"]["client_hostname"] == "all":
            self.diagnostic_return["client_hostname_all"] = True
            self.issues = True



