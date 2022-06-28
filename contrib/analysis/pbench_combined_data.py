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
            diagnostic_update, issue = check.run_diagnostic(doc)
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
    
    def add_result_data(self, doc, results_seen):
        self.transform_result(doc, results_seen)
    
    def transform_result(self, doc, results_seen):
        first_result_check = SeenResultCheck()
        diagnostic_update, issues = first_result_check.diagnostic(doc, results_seen)



        
        

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

    def __init__(self, doc):
        self.diagnostic_return = defaultdict(self.default_value)
        self.issues = False
        self.diagnostic(doc)
 
    # needs to return dictionary of form: 
    # {'diagonstic_name' : diagnostic_val}
    @staticmethod
    @abstractmethod
    def diagnostic(self, doc):
        ...
    
    @property
    def diagnostic_names(self):
        return list(self.diagnostic_return.keys())
    
    def default_value():
        return False
    
    def get_vals(self):
        return self.diagnostic_return, self.issues

class ControllerDirRunCheck(DiagnosticCheck):

    def diagnostic(self, doc):
        self.diagnostic_return = {"missing_ctrl_dir": False}
        if "controller_dir" not in doc["_source"]["@metadata"]:
            self.diagnostic_return["missing_ctrl_dir"] = True
            self.issues = True
    
    # @property
    # def diagnostic_names(self):
    #     return ["missing_ctrl_dir"]

class SosreportRunCheck(DiagnosticCheck):

    def diagnostic(self, doc):
        self.diagnostic_return["missing_sosreports"] = False
        self.diagnostic_return["non_2_sosreports"] = False
        self.diagnostic_return["sosreports_diff_hosts"] = False
        # self.issues = True
        
        # check if sosreports present
        if "sosreports" not in doc["_source"]:
            self.diagnostic_return["missing_sosreports"] = True
            self.issues = True
            # return self.diagnostic_return, self.issues
        
        # check if run has exactly 2 sosreports
        elif len(doc["_source"]["sosreports"]) != 2:
            self.diagnostic_return["non_2_sosreports"] = True
            self.issues = True
            # return self.diagnostic_return, self.issues
        
        else:
            # check if 2 sosreports have different hosts
            first = doc["_source"]["sosreports"][0]
            second = doc["_source"]["sosreports"][1]
            if first["hostname-f"] != second["hostname-f"]:
                self.diagnostic_return["sosreports_diff_hosts"] = True
                self.issues = True
                # return self.diagnostic_return, self.issues
        
        # self.issues = False
        return self.diagnostic_return, self.issues
    
    # @property
    # def diagnostic_names(self):
    #     return ["missing_sosreports", "non_2_sosreports", "sosreports_diff_hosts"]

class SeenResultCheck(DiagnosticCheck):
    
    def diagnostic(self, doc, results_seen):
        self.diagnostic_return["missing._id"] = False
        self.diagnostic_return["duplicate_result_id"] = False
        # self.issues = True

        # first check if result doc has a result id field
        if "_id" not in doc:
            self.diagnostic_return["missing._id"] = True
            self.issues = True
            # return self.diagnostic_return, self.issues
        else:
            result_id = doc["_id"]
            
            # second check if result has been seen already
            # NOTE: not sure if this check is really necessary (whether
            # a case where duplicate results occur exists)
            if result_id in results_seen:
                self.diagnostic_return["duplicate_result_id"] = True
                self.issues = True
                # return self.diagnostic_return, self.issues
            else:
                results_seen[result_id] = True

        return self.diagnostic_return, self.issues
    
    # @property
    # def diagnostic_names(self):
    #     return ["missing._id", "duplicate_result_id"]

class BaseResultCheck(DiagnosticCheck):

    def diagnostic(self, doc):
        # format missing.property/subproperty/...
        self.diagnostic_return.update(
            [
                ("missing._source", False),
                ("missing._source/run", False),
                ("missing._source/run/id", False),
                ("missing._source/run/name", False),
                ("missing._source/iteration", False),
                ("missing._source/iteration/name", False)
                ("missing._source/sample", False)
                ("missing._source/sample/name", False)
                ("missing._source/sample/measurement_type", False)
                ("missing._source/sample/measurement_title", False)
                ("missing._source/sample/measurement_idx", False)
            ]
        )
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
        else:
            return self.diagnostic_return, self.issues
            
        self.issues = True
        return self.diagnostic_return, self.issues
    
    # @property
    # def diagnostic_names(self):
    #     return 
